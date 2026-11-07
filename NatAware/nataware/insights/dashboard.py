"""Assemble everything the home screen needs in one payload."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from nataware.coaching.engine import current_plan
from nataware.config import settings
from nataware.data import queries as q
from nataware.data.store import Store
from nataware.insights.awareness import seasonal_awareness
from nataware.insights.common import current_balance, gbp, spend_between
from nataware.insights.forecast import spending_forecast
from nataware.insights.goals import goal_plans
from nataware.insights.narrate import narrator
from nataware.insights.noticed import noticed
from nataware.insights.recurring import committed_monthly, detect_recurring
from nataware.threats.macro import build_daily_macro_summary


def month_to_date(txns: list[dict[str, Any]], today: date) -> dict[str, Any]:
    start = today.replace(day=1)
    spent = spend_between(txns, start, today)
    prev_start = (start - timedelta(days=1)).replace(day=1)
    prev_same_point = spend_between(txns, prev_start, prev_start + timedelta(days=today.day - 1))
    change = round((spent - prev_same_point) / prev_same_point * 100) if prev_same_point else None
    return {"spent": spent, "previous_same_point": prev_same_point, "change_pct": change,
            "previous_month_label": f"{prev_start:%b}"}


def _narration_items(cards: list[dict], awareness: list[dict], goals: list[dict]) -> list[dict[str, Any]]:
    items = [{"id": f"noticed:{c['id']}", "kind": c["kind"], "facts": c.get("facts", {}),
              "plain": c["plain"], "detail": c["detail"]} for c in cards]
    for a in awareness:
        items.append({
            "id": f"awareness:{a['id']}",
            "kind": "seasonal",
            "facts": {k: a[k] for k in ("title", "window_label", "expected_extra", "still_to_come", "weekly_save",
                                         "last_year_spend", "contributors", "in_progress")} | {"area": a["why"]["area"]},
            "plain": f"{a['title']} usually costs you about {gbp(a['expected_extra'])} extra. "
                     f"Putting aside {gbp(a['weekly_save'])} a week covers it.",
            "detail": f"{a['why']['history']} {a['why']['area']}".strip(),
        })
    for g in goals:
        for s in g["strategies"]:
            items.append({"id": f"strategy:{g['id']}:{s['id']}", "kind": "strategy",
                          "facts": {"goal": g["name"], "title": s["title"], "monthly": s["monthly"], "evidence": s["evidence"]},
                          "plain": s["detail"], "detail": s["evidence"]})
    return items


def _apply_narration(store: Store, cards, awareness, goals, profile) -> str:
    items = _narration_items(cards, awareness, goals)
    cache = (store.get("narration") or {}).get("items", {})
    applied, missing = narrator.apply(items, cache)
    by_id = {i["id"]: i for i in applied}

    for c in cards:
        n = by_id[f"noticed:{c['id']}"]
        c.update(plain=n["plain"], detail=n["detail"], narrated=n["narrated"])
    for a in awareness:
        n = by_id[f"awareness:{a['id']}"]
        a.update(plain=n["plain"], detail=n["detail"], narrated=n["narrated"])
    for g in goals:
        for s in g["strategies"]:
            n = by_id[f"strategy:{g['id']}:{s['id']}"]
            s.update(plain=n["plain"], evidence_text=n["detail"], narrated=n["narrated"])

    def save(new: dict[str, Any]) -> None:
        current = dict((store.get("narration") or {}).get("items", {}))
        current.update(new)
        store.put("narration", {"items": current})

    context = {"first_name": (store.get("account") or {}).get("first_name"),
               "tendency": profile.tendency.value, "capacity": profile.capacity.value, "city": settings.user_city}
    return narrator.ensure(missing, context, save)


def build_dashboard(store: Store, today: date | None = None) -> dict[str, Any]:
    today = today or settings.demo_today
    profile = store.get_profile()
    if profile is None:
        return {"error": "No profile yet - complete onboarding first."}
    account = store.get("account") or {}
    txns = store.transactions
    macro = store.get("macro_summary") or build_daily_macro_summary()

    recurring = detect_recurring(txns, today)
    awareness = seasonal_awareness(txns, today, macro, store.get("set_asides") or [])
    goals = goal_plans(profile, account, txns, today)
    cards = noticed(txns, today, profile, account, recurring)
    narration_status = _apply_narration(store, cards, awareness, goals["goals"], profile)

    set_aside_weekly = sum(s["weekly"] for s in store.get("set_asides") or [])
    nudges = list(reversed(store.get("nudges") or []))

    return {
        "today": today.isoformat(),
        "account": {**account, "balance": current_balance(account, txns)},
        "profile": profile.model_dump(mode="json") | {"label": profile.label},
        "stats": {
            "month_to_date": month_to_date(txns, today),
            "committed": committed_monthly(recurring),
            "seasonal_alerts": len(awareness),
            "winter_buffer": {"weekly": set_aside_weekly, "suggested_weekly": sum(a["weekly_save"] for a in awareness)},
        },
        "goals": goals,
        "forecast": spending_forecast(txns, today, macro),
        "noticed": cards,
        "awareness": awareness,
        "threats": store.get("active_threats") or [],
        "macro_summary": {k: macro.get(k) for k in ("city", "date", "source")},
        "recurring": recurring,
        "plan": current_plan(profile, txns, today),
        "budget": q.budget_status(txns, profile.optimal_baseline.model_dump()),
        "nudges": nudges[:10],
        "narration": {"status": narration_status, "error": narrator.last_error},
    }
