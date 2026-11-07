"""'NatBot noticed' cards: unusual spending, subscriptions, cash-flow prediction, bill changes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from nataware.insights.common import (
    avg,
    current_balance,
    friendly,
    gbp,
    last_full_months,
    next_day_of_month,
    spend_between,
    watch_categories,
)


def _day_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%B}"
from nataware.profile import Profile


def _unusual_spending(txns: list[dict[str, Any]], today: date, profile: Profile) -> dict[str, Any] | None:
    cats = list(dict.fromkeys([*watch_categories(profile.tendency.value), "Eating Out", "Alcohol & Nightlife", "Groceries"]))
    day = max(1, today.day - 1)  # spending is complete up to yesterday
    month_start = today.replace(day=1)
    best = None
    for c in cats:
        now = spend_between(txns, month_start, month_start + timedelta(days=day - 1), [c])
        past = []
        for m in last_full_months(today, 3):
            s = date.fromisoformat(f"{m}-01")
            past.append(spend_between(txns, s, s + timedelta(days=day - 1), [c]))
        usual = avg(past)
        if usual < 10:
            continue
        pct = (now - usual) / usual
        if best is None or pct > best["pct"]:
            best = {"category": c, "now": now, "usual": usual, "pct": pct}
    if not best:
        return None
    pct = round(best["pct"] * 100)
    above = pct >= 10
    return {
        "id": "unusual-spending",
        "kind": "unusual_spending" if above else "on_track",
        "label": "Unusual spending" if above else "On track",
        "tone": "warning" if above else "positive",
        "plain": (
            f"{friendly(best['category']).capitalize()} is {pct}% above your usual for this point in the month."
            if above else f"Your spending is at or below your usual pace this month. Nice work."
        ),
        "detail": (
            f"{gbp(best['now'])} on {friendly(best['category'])} in the first {day} days of {today:%B}, "
            f"against a usual {gbp(best['usual'])} by this point over the last 3 months."
        ),
        "facts": {"category": best["category"], "spent_so_far": round(best["now"], 2), "usual_by_now": round(best["usual"], 2),
                  "percent_above": pct, "days_into_month": day},
        "ask": f"Why is my {friendly(best['category'])} spending up this month?",
    }


def _subscriptions(txns: list[dict[str, Any]], today: date, recurring: list[dict[str, Any]]) -> dict[str, Any] | None:
    subs = [r for r in recurring if r["category"] == "Subscriptions"]
    if not subs:
        return None
    flagged = [r for r in subs if next((t for t in txns if t["id"] == r["last_transaction_id"] and t.get("is_flagged")), None)]
    monthly = sum(r["amount"] for r in subs)
    newest = max(subs, key=lambda r: r["first_seen"])
    target = flagged or [newest]
    saving = sum(r["amount"] for r in target) * 12
    names = " and ".join(r["merchant"] for r in target[:2])
    return {
        "id": "subscriptions",
        "kind": "subscription",
        "label": "Subscriptions",
        "tone": "info",
        "plain": f"You pay for {len(subs)} subscriptions. Cancelling {names} would save {gbp(saving)} a year.",
        "detail": (
            f"{len(subs)} subscriptions cost {gbp(monthly, 2)} a month. {newest['merchant']} is the newest "
            f"(since {date.fromisoformat(newest['first_seen']):%B %Y})"
            + (f"; {names} were flagged as comfort spending." if flagged else ".")
        ),
        "facts": {"count": len(subs), "monthly_total": round(monthly, 2), "suggested": [r["merchant"] for r in target],
                  "yearly_saving": round(saving, 2)},
        "ask": "Which of my subscriptions should I cancel?",
    }


def cash_flow_prediction(
    txns: list[dict[str, Any]], today: date, account: dict[str, Any], recurring: list[dict[str, Any]]
) -> dict[str, Any]:
    balance = current_balance(account, txns)
    payday = next_day_of_month(today, int(account.get("payday_day", 28)))
    days = (payday - today).days
    bills_due = [
        r for r in recurring
        if today.isoformat() < r["next_due"] < payday.isoformat()
    ]
    bills_total = sum(r["amount"] for r in bills_due)
    # Day-to-day (non-recurring) spending rate over the last 3 months.
    months = last_full_months(today, 3)
    recurring_merchants = {r["merchant"] for r in recurring}
    start = date.fromisoformat(f"{months[0]}-01")
    end = today.replace(day=1) - timedelta(days=1)
    flexible = sum(
        t["amount"] for t in txns
        if t["direction"] == "debit" and start.isoformat() <= t["date"] <= end.isoformat()
        and t["merchant"] not in recurring_merchants
    )
    daily = flexible / ((end - start).days + 1)
    lowest = round(balance - bills_total - daily * days, 2)
    warn = lowest < 100
    return {
        "id": "cash-flow",
        "kind": "cash_flow",
        "label": "Cash-flow prediction",
        "tone": "warning" if warn else "positive",
        "plain": (
            f"Your balance could drop to about {gbp(lowest)} before payday on {payday.day} {payday:%b}."
            if warn else f"Your balance is predicted to stay above {gbp(max(0, lowest // 50 * 50))} until payday on {payday.day} {payday:%b}."
        ),
        "detail": (
            f"You have {gbp(balance, 2)} now. {len(bills_due)} bills ({gbp(bills_total)}) are due before {payday.day} {payday:%B}, "
            f"and you usually spend about {gbp(daily)} a day on everything else."
        ),
        "facts": {"balance_now": balance, "payday": payday.isoformat(), "days_to_payday": days, "bills_due": round(bills_total, 2),
                  "bills_due_count": len(bills_due), "daily_flexible_spend": round(daily, 2), "lowest_predicted": lowest},
        "ask": "Will I make it to payday?",
    }


def _bill_change(recurring: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    changed = [r for r in recurring if not r["is_savings"] and r["change"] and r["changed_on"] and r["changed_on"] >= (today - timedelta(days=45)).isoformat()]
    if not changed:
        return None
    r = max(changed, key=lambda r: abs(r["change"]))
    up = r["change"] > 0
    return {
        "id": "bill-change",
        "kind": "bill_change",
        "label": "Bill change detected",
        "tone": "warning" if up else "positive",
        "plain": f"{r['merchant']} {'rose' if up else 'dropped'} by {gbp(abs(r['change']))} this month.",
        "detail": (
            f"{r['merchant']} went from {gbp(r['previous_amount'], 2)} to {gbp(r['amount'], 2)} on "
            f"{_day_month(r['changed_on'])}."
            + (" Winter usage usually pushes it higher until March." if r["category"] == "Utilities" and up else "")
        ),
        "facts": {"merchant": r["merchant"], "from": r["previous_amount"], "to": r["amount"], "change": r["change"],
                  "category": r["category"]},
        "ask": f"Why did my {r['merchant']} bill change?",
    }


def noticed(
    txns: list[dict[str, Any]], today: date, profile: Profile, account: dict[str, Any], recurring: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cards = [
        _unusual_spending(txns, today, profile),
        _subscriptions(txns, today, recurring),
        cash_flow_prediction(txns, today, account, recurring),
        _bill_change(recurring, today),
    ]
    return [c for c in cards if c]
