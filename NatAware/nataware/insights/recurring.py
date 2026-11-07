"""Recurring payment detection (bills, subscriptions, standing orders)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import pstdev
from typing import Any

from nataware.insights.common import next_day_of_month

# Categories where a monthly payment on a stable day is almost certainly a commitment,
# even if the amount moves (energy bills vary with the season).
BILL_CATEGORIES = {
    "Rent", "Council Tax", "Utilities", "Phone & Internet", "Subscriptions",
    "Fitness", "Debt Repayment", "Savings Transfer",
}


def detect_recurring(txns: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    by_merchant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in txns:
        if t["direction"] == "debit":
            by_merchant[t["merchant"]].append(t)

    out = []
    for merchant, items in by_merchant.items():
        items = sorted(items, key=lambda t: t["date"])
        months = sorted({t["date"][:7] for t in items})
        if len(months) < 3 or len(items) > len(months) * 1.5:  # roughly one per month
            continue
        recent = items[-6:]
        days = [int(t["date"][8:10]) for t in recent]
        if pstdev(days) > 3:
            continue
        amounts = [t["amount"] for t in recent]
        category = recent[-1]["category"]
        if category not in BILL_CATEGORIES:
            mid = sorted(amounts)[len(amounts) // 2]
            if any(abs(a - mid) / mid > 0.15 for a in amounts):
                continue
        last = recent[-1]
        if (today - date.fromisoformat(last["date"])).days > 45:  # cancelled / lapsed
            continue
        prev = recent[-2] if len(recent) > 1 else None
        change = round(last["amount"] - prev["amount"], 2) if prev else 0.0
        day = round(sum(days[-3:]) / len(days[-3:]))
        out.append({
            "merchant": merchant,
            "category": category,
            "amount": last["amount"],
            "previous_amount": prev["amount"] if prev else None,
            "change": change if abs(change) >= 0.5 else 0.0,
            "changed_on": last["date"] if abs(change) >= 0.5 else None,
            "day_of_month": day,
            "next_due": next_day_of_month(today, day).isoformat(),
            "first_seen": items[0]["date"],
            "is_savings": category == "Savings Transfer",
            "last_transaction_id": last["id"],
        })
    return sorted(out, key=lambda r: -r["amount"])


def committed_monthly(recurring: list[dict[str, Any]]) -> dict[str, Any]:
    bills = [r for r in recurring if not r["is_savings"]]
    return {"total": round(sum(r["amount"] for r in bills), 2), "count": len(bills)}
