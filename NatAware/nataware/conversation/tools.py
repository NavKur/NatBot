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
    {
        "name": "get_goals_and_strategies",
        "description": (
            "The user's savings goals with progress, how long they'll take on the current path, and recommended "
            "strategies (each with a £/month value computed from their own spending) and the faster timeline if "
            "they adopt them. Use for any question about goals, saving faster or 'how do I get to X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"goal_id": {"type": "string", "description": "Optional: only this goal."}},
        },
    },
    {
        "name": "get_spending_forecast",
        "description": (
            "Predicted monthly spending for the rest of this month and the next 4 months, with a likely range "
            "and the drivers (seasonal patterns from last year, announced price rises). Use for 'what will I "
            "spend', 'how will December look', 'financial time travel' questions."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_seasonal_outlook",
        "description": (
            "Upcoming seasonal costs for this user (e.g. Christmas, heating, cold and flu season): expected "
            "extra cost from their own history last year plus local news, confidence, and a suggested weekly "
            "amount to put aside."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_insights",
        "description": (
            "What NatBot has noticed right now: unusual spending this month, subscriptions, a cash-flow "
            "prediction to next payday, and bill changes."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_aside_for_event",
        "description": "Start (or change) a weekly set-aside towards an upcoming seasonal cost, when the user agrees to it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "id from get_seasonal_outlook, e.g. 'christmas'."},
                "weekly": {"type": "number", "exclusiveMinimum": 0, "description": "£ per week."},
            },
            "required": ["event_id", "weekly"],
        },
    },
    {
        "name": "update_goal",
        "description": (
            "Add a new savings goal or change an existing one's name or target, when the user tells you about it. "
            "Pass goal_id to change an existing goal; omit it to add a new one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string"},
                "name": {"type": "string"},
                "kind": {"type": "string", "enum": ["house", "emergency", "debt", "travel", "education", "car", "family",
                                                    "wedding", "retirement", "other"]},
                "target": {"type": "number", "exclusiveMinimum": 0, "description": "Target amount in £."},
            },
            "required": ["name", "target"],
        },
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


def _get_goals_and_strategies(goal_id: str | None = None) -> dict[str, Any]:
    from nataware.insights.goals import goal_plans

    store = get_store()
    profile = store.get_profile()
    if profile is None:
        return {"error": "No profile yet."}
    plans = goal_plans(profile, store.get("account") or {}, store.transactions, settings.demo_today)
    if goal_id:
        plans["goals"] = [g for g in plans["goals"] if g["id"] == goal_id] or plans["goals"]
    plans["note"] = (
        "current_path_months uses usual_monthly savings only; plan_months assumes every strategy is adopted. "
        "The 'lisa' strategy is a 25% government bonus on deposits capped at £83/month; eligibility applies."
    )
    return plans


def _get_spending_forecast() -> dict[str, Any]:
    from nataware.insights.forecast import spending_forecast
    from nataware.threats.macro import build_daily_macro_summary

    store = get_store()
    return spending_forecast(store.transactions, settings.demo_today, store.get("macro_summary") or build_daily_macro_summary())


def _get_seasonal_outlook() -> dict[str, Any]:
    from nataware.insights.awareness import seasonal_awareness
    from nataware.threats.macro import build_daily_macro_summary

    store = get_store()
    events = seasonal_awareness(store.transactions, settings.demo_today,
                                store.get("macro_summary") or build_daily_macro_summary(), store.get("set_asides") or [])
    return {"events": events}


def _get_insights() -> dict[str, Any]:
    from nataware.insights.noticed import noticed
    from nataware.insights.recurring import detect_recurring

    store = get_store()
    profile = store.get_profile()
    if profile is None:
        return {"error": "No profile yet."}
    recurring = detect_recurring(store.transactions, settings.demo_today)
    return {"insights": noticed(store.transactions, settings.demo_today, profile, store.get("account") or {}, recurring)}


def set_aside(event_id: str, weekly: float) -> dict[str, Any]:
    from nataware.insights.awareness import load_events

    if event_id not in {e["id"] for e in load_events()}:
        raise ValueError(f"Unknown seasonal event {event_id!r}")
    store = get_store()
    entry = {"event_id": event_id, "weekly": round(float(weekly), 2), "created_at": datetime.now().isoformat(timespec="seconds")}
    rest = [s for s in store.get("set_asides") or [] if s["event_id"] != event_id]
    store.put("set_asides", [*rest, entry])
    return {"set_aside": entry, "total_weekly": round(sum(s["weekly"] for s in [*rest, entry]), 2)}


def _set_aside_for_event(event_id: str, weekly: float) -> dict[str, Any]:
    return set_aside(event_id, weekly)


def _update_goal(name: str, target: float, kind: str = "other", goal_id: str | None = None) -> dict[str, Any]:
    from nataware.profile import Goal

    store = get_store()
    profile = store.get_profile()
    if profile is None:
        return {"error": "No profile yet."}
    goals = list(profile.goals)
    existing = next((g for g in goals if g.id == goal_id), None) if goal_id else None
    if existing:
        updated = existing.model_copy(update={"name": name, "target": float(target), "kind": kind or existing.kind})
        goals = [updated if g.id == existing.id else g for g in goals]
    else:
        updated = Goal(name=name, target=float(target), kind=kind)
        if any(g.id == updated.id for g in goals):
            updated = updated.model_copy(update={"id": f"{updated.id}-{len(goals) + 1}"})
        goals.append(updated)
    store.set_profile(profile.model_copy(update={"goals": goals}))
    return {"goal": updated.model_dump(), "goals": [g.model_dump() for g in goals]}


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
    "get_goals_and_strategies": _get_goals_and_strategies,
    "get_spending_forecast": _get_spending_forecast,
    "get_seasonal_outlook": _get_seasonal_outlook,
    "get_insights": _get_insights,
    "set_aside_for_event": _set_aside_for_event,
    "update_goal": _update_goal,
}
