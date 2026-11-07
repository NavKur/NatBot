"""Background tasks wiring Phases 2-4 together.

Each task's body is real orchestration; the "intelligence" inside (tagging, threat
scoring, nudge writing) is the deterministic demo version from its module.
"""

from __future__ import annotations

import logging
from typing import Any

from nataware.coaching import engine as coaching
from nataware.coaching.notifications import deliver
from nataware.data import queries as q
from nataware.data.store import get_store
from nataware.ingestion.tagging import BATCH_SIZE, tag_batch
from nataware.threats.engine import calculate_threats
from nataware.threats.macro import build_daily_macro_summary
from nataware.worker.celery_app import celery_app

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------- Phase 2
def _tag_untagged(batch_size: int = BATCH_SIZE) -> int:
    store = get_store()
    profile = store.get_profile()
    if profile is None:
        return 0
    untagged = [t for t in store.transactions if not t.get("tagged")]
    for i in range(0, len(untagged), batch_size):
        for result in tag_batch(untagged[i : i + batch_size], profile.tendency):
            store.update_transaction(
                result["id"],
                tagged=True,
                is_flagged=result["is_flagged"],
                highlight_reason=result["highlight_reason"],
            )
    store.save()
    return len(untagged)


@celery_app.task(name="tagging.tag_untagged")
def tag_untagged_transactions(batch_size: int = BATCH_SIZE) -> int:
    return _tag_untagged(batch_size)


@celery_app.task(name="tagging.retag_all")
def retag_all_transactions() -> int:
    """Profile changed (e.g. after onboarding): re-run tagging against the new Tendency."""
    store = get_store()
    for t in store.transactions:
        t["tagged"] = False
    return _tag_untagged()


@celery_app.task(name="ingestion.ingest_statement")
def ingest_statement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    store = get_store()
    added = [store.add_transaction(r) for r in rows]
    _tag_untagged()
    ids = {t["id"] for t in added}
    tagged = [q.public_view(t) for t in store.transactions if t["id"] in ids]
    return {"added": len(added), "flagged": sum(t["is_flagged"] for t in tagged), "transactions": tagged}


@celery_app.task(name="ingestion.ingest_transaction")
def ingest_transaction(txn: dict[str, Any]) -> dict[str, Any]:
    """A single new transaction (webhook / voice log): store, tag, then check the transaction trigger."""
    store = get_store()
    txn_id = store.add_transaction(txn)["id"]
    _tag_untagged()
    saved = store.get_transaction(txn_id)
    plan = coaching.current_plan(store.get_profile(), store.transactions)

    nudge = None
    if coaching.transaction_trigger_fires(saved, plan):
        nudge = _intervene("transaction", {"transaction": q.public_view(saved)}, plan)
    return {"transaction": q.public_view(saved), "plan": plan, "nudge": nudge}


# ---------------------------------------------------------------------- Phase 3
@celery_app.task(name="threats.refresh")
def refresh_threats() -> list[dict[str, Any]]:
    store = get_store()
    profile = store.get_profile()
    if profile is None:
        return []
    macro = build_daily_macro_summary()
    budget = q.budget_status(store.transactions, profile.optimal_baseline.model_dump())
    previous = {t["threat_id"] for t in store.get("active_threats") or []}
    threats = calculate_threats(profile, macro, budget)
    store.put("macro_summary", macro)
    store.put("active_threats", threats)

    # Phase 4 macro trigger: a NEW high-priority threat was logged.
    plan = coaching.current_plan(profile, store.transactions)
    for th in threats:
        if th["priority"] == "high" and th["threat_id"] not in previous:
            _intervene("macro", {"threat": th}, plan)
    return threats


# ---------------------------------------------------------------------- Phase 4
def _intervene(trigger: str, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    return deliver(coaching.generate_nudge(trigger, context, plan))


@celery_app.task(name="coaching.generate_intervention")
def generate_intervention(trigger: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Manually fire a trigger (used by the API / CLI to demo each trigger type)."""
    store = get_store()
    plan = coaching.current_plan(store.get_profile(), store.transactions)
    context = dict(context or {})
    if trigger == "transaction" and "transaction" not in context:
        flagged = q.filter_transactions(store.transactions, flagged_only=True)
        if not flagged:
            raise ValueError("No flagged transactions to build a transaction nudge from.")
        context["transaction"] = q.public_view(flagged[-1])
    if trigger == "macro" and "threat" not in context:
        threats = store.get("active_threats") or refresh_threats()
        if not threats:
            raise ValueError("No active threats to build a macro nudge from.")
        context["threat"] = threats[0]
    return _intervene(trigger, context, plan)


@celery_app.task(name="coaching.weekend_prep")
def weekend_prep() -> dict[str, Any]:
    return generate_intervention("temporal")


def bootstrap() -> None:
    """Make sure the demo store is tagged and has threats (idempotent)."""
    store = get_store()
    if any(not t.get("tagged") for t in store.transactions):
        tag_untagged_transactions.delay()
    if not store.get("active_threats"):
        refresh_threats.delay()
