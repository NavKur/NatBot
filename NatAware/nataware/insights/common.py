"""Small date / aggregation helpers shared by the insight modules."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Any, Iterable


# Money that leaves the current account but isn't "spending".
NOT_SPENDING = {"Savings Transfer"}


def ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def ym_add(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_label(month: str, short: bool = True) -> str:
    m = int(month[5:7])
    return calendar.month_abbr[m] if short else calendar.month_name[m]


def days_in_month(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def last_full_months(today: date, n: int) -> list[str]:
    current = ym(today)
    return [ym_add(current, -i) for i in range(n, 0, -1)]


def is_spending(t: dict[str, Any]) -> bool:
    return t["direction"] == "debit" and t["category"] not in NOT_SPENDING


def spend_by_month(txns: Iterable[dict[str, Any]], categories: Iterable[str] | None = None) -> dict[str, float]:
    cats = set(categories) if categories else None
    out: dict[str, float] = defaultdict(float)
    for t in txns:
        if not is_spending(t) or (cats and t["category"] not in cats):
            continue
        out[t["date"][:7]] += t["amount"]
    return dict(out)


def spend_between(
    txns: Iterable[dict[str, Any]], start: date, end: date, categories: Iterable[str] | None = None
) -> float:
    """Spending in [start, end] inclusive."""
    cats = set(categories) if categories else None
    s, e = start.isoformat(), end.isoformat()
    return round(
        sum(t["amount"] for t in txns if is_spending(t) and s <= t["date"] <= e and (not cats or t["category"] in cats)),
        2,
    )


def months_with_data(txns: list[dict[str, Any]]) -> list[str]:
    return sorted({t["date"][:7] for t in txns})


def avg(values: Iterable[float]) -> float:
    vals = list(values)
    return mean(vals) if vals else 0.0


def current_balance(account: dict[str, Any], txns: list[dict[str, Any]]) -> float:
    """Seeded balance, adjusted for anything logged after it was taken."""
    as_of = account.get("balance_as_of", "")
    delta = sum(
        (t["amount"] if t["direction"] == "credit" else -t["amount"]) for t in txns if t["date"] > as_of
    )
    return round(account.get("balance", 0.0) + delta, 2)


def next_day_of_month(today: date, day: int) -> date:
    """Next date strictly after `today` that falls on `day` (clamped to month length)."""
    y, m = today.year, today.month
    for _ in range(2):
        candidate = date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if candidate > today:
            return candidate
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return today + timedelta(days=30)


def gbp(v: float, decimals: int = 0) -> str:
    return f"£{v:,.{decimals}f}"


def watch_categories(tendency: str) -> list[str]:
    from nataware.coaching.engine import load_transition_matrix

    return load_transition_matrix()["tendencies"][tendency]["watch_categories"]



FRIENDLY = {
    "Takeaway & Delivery": "takeaways and delivery",
    "Shopping - Online": "online shopping",
    "Shopping - Clothing": "clothes shopping",
    "Alcohol & Nightlife": "drinks and nights out",
    "Cash Withdrawal": "cash withdrawals",
    "Health & Pharmacy": "pharmacy",
    "Phone & Internet": "phone and internet",
}


def friendly(category: str) -> str:
    """Category name as it reads mid-sentence ("online shopping")."""
    return FRIENDLY.get(category, category.lower())
