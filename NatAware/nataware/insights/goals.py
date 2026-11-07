"""Goal projections and recommended strategies.

Each strategy's monthly value is computed from the user's own transactions (e.g. half of
what they actually spend on delivery, the round-ups their real card payments would make).
The UI toggles strategies on and off and re-projects the goal instantly from these numbers.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from nataware.insights.common import avg, gbp, last_full_months, spend_by_month
from nataware.profile import Goal, Profile

# Payments that don't go through the card (so don't generate round-ups).
NO_ROUND_UP = {"Rent", "Council Tax", "Utilities", "Phone & Internet", "Debt Repayment", "Savings Transfer", "Subscriptions", "Income"}

# Lifetime ISA: 25% government bonus on up to £4,000 a year (max £1,000 bonus).
LISA_RATE = 0.25
LISA_CAP_MONTHLY = round(1000 / 12, 2)

# Tendency-specific habit swap: (category list, share of spend saved, title, how)
HABIT_SWAPS: dict[str, tuple[list[str], float, str, str]] = {
    "The Comfort-Buyer": (["Takeaway & Delivery"], 0.4, "Batch cook twice a week",
                          "Swap two delivery nights a week for a batch-cooked meal."),
    "The Status-Seeker": (["Shopping - Clothing", "Eating Out"], 0.35, "Use a 24-hour rule over £30",
                          "Wait a day before any purchase over £30 and ask if you'd still buy it if no one saw it."),
    "The Experience-Junkie": (["Alcohol & Nightlife"], 0.3, "Set a fixed weekend fun budget",
                              "Load a set amount onto a separate card each weekend and leave the main card at home."),
    "The Panic-Hoarder": (["Cash Withdrawal"], 0.5, "Move idle cash into savings",
                          "Cap cash withdrawals at £20 and move the rest into an easy-access savings pot."),
}


def usual_monthly_savings(txns: list[dict[str, Any]], today: date) -> float:
    months = last_full_months(today, 3)
    totals = {m: 0.0 for m in months}
    for t in txns:
        if t["category"] == "Savings Transfer" and t["direction"] == "debit" and t["date"][:7] in totals:
            totals[t["date"][:7]] += t["amount"]
    return round(avg(totals.values()), 2)


def allocate_saved(goals: list[Goal], savings_balance: float) -> dict[str, float]:
    """Goals without an explicit `saved` share whatever is left in the savings pot, by target size."""
    explicit = {g.id: g.saved for g in goals if g.saved is not None}
    left = max(0.0, savings_balance - sum(explicit.values()))
    open_goals = [g for g in goals if g.saved is None]
    weight = sum(g.target for g in open_goals) or 1
    out = dict(explicit)
    for g in open_goals:
        out[g.id] = min(g.target, round(left * g.target / weight / 10) * 10)
    return out


def _monthly_avg(txns: list[dict[str, Any]], today: date, categories: list[str]) -> float:
    by_month = spend_by_month(txns, categories)
    return avg(by_month.get(m, 0.0) for m in last_full_months(today, 3))


def _round_ups(txns: list[dict[str, Any]], today: date) -> float:
    months = set(last_full_months(today, 3))
    total = sum(
        math.ceil(t["amount"]) - t["amount"]
        for t in txns
        if t["direction"] == "debit" and t["date"][:7] in months and t["category"] not in NO_ROUND_UP
    )
    return round(total / 3, 2)


def _comfort_subscriptions(txns: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Subscriptions behavioural tagging flagged, else overlapping streaming services beyond the first two."""
    recent_month = last_full_months(today, 1)[0]
    latest: dict[str, dict[str, Any]] = {}
    for t in txns:
        if t["category"] == "Subscriptions" and t["direction"] == "debit" and t["date"][:7] >= recent_month:
            latest[t["merchant"]] = t
    flagged = [t for t in latest.values() if t.get("is_flagged")]
    if flagged:
        return flagged
    streaming = sorted((t for t in latest.values() if "streaming" in t.get("tags", [])), key=lambda t: t["amount"])
    return streaming[:-2] if len(streaming) > 2 else []


def strategies_for(goal: Goal, profile: Profile, txns: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    if goal.kind == "house":
        out.append({
            "id": "lisa",
            "title": "Use a government-boosted savings account",
            "detail": "A Lifetime ISA adds a 25% bonus to what you put in (up to £1,000 a year) if you're 18 to 39 "
                      "and buying your first home under £450,000. Check you're eligible before opening one.",
            "kind": "bonus",
            "rate": LISA_RATE,
            "cap_monthly": LISA_CAP_MONTHLY,
            "monthly": None,  # depends on what else is selected; the UI computes it
            "evidence": "Government bonus: 25% of your deposits, up to £83 a month.",
        })

    subs = _comfort_subscriptions(txns, today)
    if subs:
        names = [s["merchant"] for s in subs]
        monthly = round(sum(s["amount"] for s in subs), 2)
        label = " and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " and " + names[-1]
        out.append({
            "id": "cancel-subscriptions",
            "title": f"Cancel {label}",
            "detail": f"NatBot flagged {label} as comfort subscriptions that overlap with services you already pay for.",
            "kind": "add",
            "monthly": monthly,
            "evidence": f"{label} cost you {gbp(monthly, 2)} a month.",
            "transaction_ids": [s["id"] for s in subs],
        })

    round_ups = _round_ups(txns, today)
    if round_ups >= 5:
        out.append({
            "id": "round-ups",
            "title": "Turn on round-ups",
            "detail": "Rounds each card payment up to the nearest pound and saves the difference.",
            "kind": "add",
            "monthly": round_ups,
            "evidence": f"Your card payments over the last 3 months would have rounded up {gbp(round_ups, 2)} a month.",
        })

    swap = HABIT_SWAPS.get(profile.tendency.value)
    if swap:
        cats, share, title, how = swap
        spend = _monthly_avg(txns, today, cats)
        monthly = round(spend * share / 5) * 5
        if monthly >= 5:
            out.append({
                "id": "habit-swap",
                "title": title,
                "detail": how,
                "kind": "add",
                "monthly": float(monthly),
                "evidence": f"You average {gbp(spend)} a month on {', '.join(c.lower() for c in cats)}; "
                            f"cutting {share * 100:.0f}% frees about {gbp(monthly)}.",
                "categories": cats,
            })
    return out


def project_months(remaining: float, monthly: float) -> int | None:
    if remaining <= 0:
        return 0
    if monthly <= 0:
        return None
    return math.ceil(remaining / monthly)


def plan_monthly(strategies: list[dict[str, Any]], usual: float, selected: set[str] | None = None) -> float:
    """Usual savings + selected strategies (bonus strategies apply to everything else)."""
    chosen = [s for s in strategies if selected is None or s["id"] in selected]
    adds = sum(s["monthly"] or 0 for s in chosen if s["kind"] == "add")
    base = usual + adds
    bonus = sum(min(base * s["rate"], s["cap_monthly"]) for s in chosen if s["kind"] == "bonus")
    return round(base + bonus, 2)


def goal_plans(profile: Profile, account: dict[str, Any], txns: list[dict[str, Any]], today: date) -> dict[str, Any]:
    usual = usual_monthly_savings(txns, today)
    saved_map = allocate_saved(profile.goals, float(account.get("savings_balance", 0)))
    plans = []
    for g in profile.goals:
        saved = saved_map.get(g.id, 0.0)
        remaining = max(0.0, g.target - saved)
        strategies = strategies_for(g, profile, txns, today)
        with_plan = plan_monthly(strategies, usual)
        plans.append({
            **g.model_dump(),
            "saved": saved,
            "remaining": round(remaining, 2),
            "progress": round(saved / g.target, 3) if g.target else 0,
            "usual_monthly": usual,
            "strategies": strategies,
            "current_path_months": project_months(remaining, usual),
            "plan_monthly": with_plan,
            "plan_months": project_months(remaining, with_plan),
        })
    return {"usual_monthly_savings": usual, "savings_balance": account.get("savings_balance", 0), "goals": plans}
