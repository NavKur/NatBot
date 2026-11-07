"""Read-side queries over transactions: filtering, aggregation, budget state."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from nataware.config import settings

CATEGORIES: dict[str, str] = {
    # category -> budget bucket
    "Rent": "needs",
    "Council Tax": "needs",
    "Utilities": "needs",
    "Phone & Internet": "needs",
    "Groceries": "needs",
    "Transport": "needs",
    "Health & Pharmacy": "needs",
    "Pets": "needs",
    "Home & Repairs": "needs",
    "Debt Repayment": "savings",
    "Savings Transfer": "savings",
    "Takeaway & Delivery": "wants",
    "Eating Out": "wants",
    "Alcohol & Nightlife": "wants",
    "Shopping - Clothing": "wants",
    "Shopping - Online": "wants",
    "Subscriptions": "wants",
    "Entertainment": "wants",
    "Travel": "wants",
    "Fitness": "wants",
    "Cash Withdrawal": "wants",
    "Income": "income",
}


def to_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def money(value: float) -> str:
    return f"{settings.currency_symbol}{value:,.2f}"


def filter_transactions(
    txns: Iterable[dict[str, Any]],
    *,
    query: str | None = None,
    categories: list[str] | None = None,
    date_from: str | date | None = None,
    date_to: str | date | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    flagged_only: bool = False,
    direction: str | None = "debit",
) -> list[dict[str, Any]]:
    """Filter transactions. `query` tokens must ALL appear in merchant / category / tags."""
    d_from, d_to = to_date(date_from), to_date(date_to)
    cats = {c.lower() for c in categories} if categories else None
    tokens = [t for t in (query or "").lower().split() if t]

    out = []
    for t in txns:
        if direction and t["direction"] != direction:
            continue
        if cats and t["category"].lower() not in cats:
            continue
        d = to_date(t["date"])
        if d_from and d < d_from:
            continue
        if d_to and d > d_to:
            continue
        if min_amount is not None and t["amount"] < min_amount:
            continue
        if max_amount is not None and t["amount"] > max_amount:
            continue
        if flagged_only and not t.get("is_flagged"):
            continue
        if tokens:
            haystack = " ".join([t["merchant"], t["category"], *t.get("tags", [])]).lower()
            if not all(tok in haystack for tok in tokens):
                continue
        out.append(t)
    return out


def summarise(txns: Iterable[dict[str, Any]], group_by: str = "category") -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in txns:
        if group_by == "month":
            key = t["date"][:7]
        elif group_by == "bucket":
            key = CATEGORIES.get(t["category"], "wants")
        elif group_by == "merchant":
            key = t["merchant"]
        else:
            key = t["category"]
        groups[key]["total"] += t["amount"]
        groups[key]["count"] += 1
    rows = [{"group": k, "total": round(v["total"], 2), "count": v["count"]} for k, v in groups.items()]
    sort_key = (lambda r: r["group"]) if group_by == "month" else (lambda r: -r["total"])
    return sorted(rows, key=sort_key)


def previous_month(today: date | None = None) -> str:
    today = today or settings.demo_today
    first = today.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


def budget_status(txns: list[dict[str, Any]], baseline: dict[str, float], month: str | None = None) -> dict[str, Any]:
    """Actual Needs/Wants/Savings split for a month, against the profile's optimal baseline."""
    month = month or previous_month()
    in_month = [t for t in txns if t["date"].startswith(month)]
    # Money moved back from a savings pot isn't income.
    income = sum(t["amount"] for t in in_month if t["direction"] == "credit" and t["category"] != "Savings Transfer")
    buckets = {"needs": 0.0, "wants": 0.0, "savings": 0.0}
    for t in in_month:
        if t["direction"] != "debit":
            continue
        buckets[CATEGORIES.get(t["category"], "wants")] += t["amount"]

    def pct(v: float) -> float:
        return round(v * 100 / income, 1) if income else 0.0

    return {
        "month": month,
        "income": round(income, 2),
        "spent_total": round(sum(buckets.values()), 2),
        "actual": {k: {"amount": round(v, 2), "percent_of_income": pct(v)} for k, v in buckets.items()},
        "target_percent": baseline,
        "gap_percent": {k: round(pct(buckets[k]) - float(baseline.get(k, 0)), 1) for k in buckets},
        "unallocated": round(income - sum(buckets.values()), 2),
    }


def week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or settings.demo_today
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def public_view(t: dict[str, Any]) -> dict[str, Any]:
    """The subset of a transaction the LLM (and front end) needs."""
    return {
        "id": t["id"],
        "date": t["date"],
        "time": t.get("time"),
        "merchant": t["merchant"],
        "amount": t["amount"],
        "direction": t["direction"],
        "category": t["category"],
        "is_flagged": t.get("is_flagged", False),
        "highlight_reason": t.get("highlight_reason"),
    }
