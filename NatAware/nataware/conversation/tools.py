"""Tools NatBot can call during the coaching conversation.

The tools are real; the data behind them is fake (see `data/seed/`). Each tool returns a
JSON-serialisable dict. Results that contain a `transactions` list are also what the CLI
renders on screen, and what a front end would render via the API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from nataware.config import settings
from nataware.data import queries as q
from nataware.data.store import get_store

_CATEGORY_ENUM = [c for c in q.CATEGORIES]
_DATE = {"type": "string", "description": "ISO date, YYYY-MM-DD (inclusive)."}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_transactions",
        "description": (
            "Search the user's transactions. Combine categories, a keyword and a date range. "
            "Returns matching transactions with a count and total. Use direction='credit' for money in."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword(s) matched against merchant name, category and tags, e.g. 'deliveroo', 'pub', 'late-night'.",
                },
                "categories": {"type": "array", "items": {"type": "string", "enum": _CATEGORY_ENUM}},
                "date_from": _DATE,
                "date_to": _DATE,
                "min_amount": {"type": "number"},
                "max_amount": {"type": "number"},
                "flagged_only": {"type": "boolean", "description": "Only behaviourally flagged transactions."},
                "direction": {"type": "string", "enum": ["debit", "credit"], "default": "debit"},
                "limit": {"type": "integer", "default": 60, "maximum": 200},
            },
        },
    },
    {
        "name": "highlight_transactions",
        "description": (
            "Highlight specific transactions on the user's screen. Call this whenever the user asks to "
            "see, show, list, highlight or point out transactions, after finding their IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "label": {"type": "string", "description": "Short title, e.g. 'Alcohol - October'."},
                "reason": {"type": "string", "description": "Optional one-line note shown with the highlight."},
            },
            "required": ["transaction_ids", "label"],
        },
    },
    {
        "name": "get_spending_summary",
        "description": "Total spending grouped by category, merchant, month or budget bucket (needs/wants/savings).",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["category", "merchant", "month", "bucket"]},
                "date_from": _DATE,
                "date_to": _DATE,
                "categories": {"type": "array", "items": {"type": "string", "enum": _CATEGORY_ENUM}},
                "top_n": {"type": "integer", "default": 10},
            },
            "required": ["group_by"],
        },
    },
    {
        "name": "get_budget_status",
        "description": "Actual Needs/Wants/Savings split for a month versus the user's optimal baseline.",
        "input_schema": {
            "type": "object",
            "properties": {"month": {"type": "string", "description": "YYYY-MM. Defaults to last full month."}},
        },
    },
    {
        "name": "get_behavioural_flags",
        "description": "Transactions NatAware's behavioural tagging flagged against the user's tendency, with the reason for each.",
        "input_schema": {
            "type": "object",
            "properties": {"date_from": _DATE, "date_to": _DATE, "limit": {"type": "integer", "default": 25}},
        },
    },
    {
        "name": "get_active_threats",
        "description": "Upcoming local financial threats (weather, prices, tax) and the recommended budget shift for each.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_coaching_plan",
        "description": "The user's current coaching stage, this week's micro-goal and limit, and progress against it.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "log_transaction",
        "description": (
            "Record a purchase the user tells you they just made. Runs behavioural tagging and the "
            "transaction trigger; returns any coaching nudge that fired."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "merchant": {"type": "string"},
                "amount": {"type": "number", "exclusiveMinimum": 0},
                "category": {"type": "string", "enum": [c for c in _CATEGORY_ENUM if c != "Income"]},
                "date": _DATE,
                "time": {"type": "string", "description": "HH:MM, 24h."},
            },
            "required": ["merchant", "amount", "category"],
        },
    },
    {
        "name": "get_recent_nudges",
        "description": "The most recent coaching nudges NatAware has sent the user.",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}},
    },
]


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    return handler(**(args or {}))


# ---------------------------------------------------------------------- handlers
def _search_transactions(limit: int = 60, **filters: Any) -> dict[str, Any]:
    store = get_store()
    matches = q.filter_transactions(store.transactions, **filters)
    limit = max(1, min(int(limit), 200))
    return {
        "match_count": len(matches),
        "total": round(sum(t["amount"] for t in matches), 2),
        "filters": filters,
        "truncated": len(matches) > limit,
        "transactions": [q.public_view(t) for t in matches[:limit]],
    }


def _highlight_transactions(transaction_ids: list[str], label: str, reason: str | None = None) -> dict[str, Any]:
    store = get_store()
    found, missing = [], []
    for tid in dict.fromkeys(transaction_ids):  # de-dupe, keep order
        txn = store.get_transaction(tid)
        (found.append(txn) if txn else missing.append(tid))
    highlight = {
        "label": label,
        "reason": reason,
        "transaction_ids": [t["id"] for t in found],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    store.append("highlights", highlight)
    return {
        "label": label,
        "reason": reason,
        "highlighted_count": len(found),
        "total": round(sum(t["amount"] for t in found), 2),
        "missing_ids": missing,
        "transactions": [q.public_view(t) for t in found],
    }


def _get_spending_summary(group_by: str, top_n: int = 10, **filters: Any) -> dict[str, Any]:
    store = get_store()
    txns = q.filter_transactions(store.transactions, **filters)
    rows = q.summarise(txns, group_by)
    return {
        "group_by": group_by,
        "filters": filters,
        "total": round(sum(t["amount"] for t in txns), 2),
        "rows": rows if group_by == "month" else rows[: max(1, int(top_n))],
        "group_count": len(rows),
    }


def _get_budget_status(month: str | None = None) -> dict[str, Any]:
    store = get_store()
    profile = store.get_profile()
    baseline = profile.optimal_baseline.model_dump() if profile else {"needs": 50, "wants": 30, "savings": 20}
    return q.budget_status(store.transactions, baseline, month)


def _get_behavioural_flags(date_from: str | None = None, date_to: str | None = None, limit: int = 25) -> dict[str, Any]:
    store = get_store()
    flagged = q.filter_transactions(store.transactions, date_from=date_from, date_to=date_to, flagged_only=True)
    flagged = sorted(flagged, key=lambda t: t["date"], reverse=True)
    profile = store.get_profile()
    return {
        "tendency": profile.tendency.value if profile else None,
        "flag_count": len(flagged),
        "total": round(sum(t["amount"] for t in flagged), 2),
        "transactions": [q.public_view(t) for t in flagged[: max(1, int(limit))]],
    }


def _get_active_threats() -> dict[str, Any]:
    from nataware.worker.tasks import refresh_threats

    store = get_store()
    if not store.get("active_threats"):
        refresh_threats.delay()
    return {"city": settings.user_city, "threats": store.get("active_threats") or []}


def _get_coaching_plan() -> dict[str, Any]:
    from nataware.coaching.engine import current_plan

    store = get_store()
    return current_plan(store.get_profile(), store.transactions)


def _log_transaction(
    merchant: str, amount: float, category: str, date: str | None = None, time: str | None = None
) -> dict[str, Any]:
    from nataware.worker.tasks import ingest_transaction

    txn = {
        "date": date or settings.demo_today.isoformat(),
        "time": time or datetime.now().strftime("%H:%M"),
        "merchant": merchant,
        "amount": round(float(amount), 2),
        "currency": "GBP",
        "direction": "debit",
        "category": category,
        "tags": ["logged-by-voice"],
        "source": "natbot",
    }
    return ingest_transaction.delay(txn).get()


def _get_recent_nudges(limit: int = 5) -> dict[str, Any]:
    nudges = get_store().get("nudges") or []
    return {"nudges": list(reversed(nudges))[: max(1, int(limit))]}


_HANDLERS = {
    "search_transactions": _search_transactions,
    "highlight_transactions": _highlight_transactions,
    "get_spending_summary": _get_spending_summary,
    "get_budget_status": _get_budget_status,
    "get_behavioural_flags": _get_behavioural_flags,
    "get_active_threats": _get_active_threats,
    "get_coaching_plan": _get_coaching_plan,
    "log_transaction": _log_transaction,
    "get_recent_nudges": _get_recent_nudges,
}
