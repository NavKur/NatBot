"""Monthly spending forecast ("financial time travel").

Method (deliberately simple and explainable):
  baseline   = average spending over the last 3 full months
  season(m)  = spending in the same month last year / average of last year's matching
               baseline months (so a December that ran 40% hot last year runs hot again)
  forecast(m)= baseline x season(m) + announced price rises (Phase 3 macro summary)
  range      = +/- the typical month-to-month swing, widening further out
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import pstdev
from typing import Any

from nataware.insights.common import (
    avg,
    last_full_months,
    month_label,
    months_with_data,
    spend_between,
    spend_by_month,
    ym,
    ym_add,
)

HISTORY_MONTHS = 8
HORIZON = 4  # months after the current one


def _price_rise_for_month(month: str, macro: dict[str, Any] | None, monthly_by_cat: dict[str, float]) -> list[dict[str, Any]]:
    """Extra monthly cost from announced price changes that start on or before `month`."""
    if not macro:
        return []
    out = []
    for item in macro.get("economic_news", []):
        pct = item.get("price_change_pct")
        if not pct or item.get("starts", "9999")[:7] > month:
            continue
        base = sum(monthly_by_cat.get(c, 0.0) for c in item.get("affects", []))
        extra = round(base * pct / 100, 2)
        if extra >= 1:
            out.append({"label": item["headline"], "amount": extra, "source_id": item["id"]})
    return out


def spending_forecast(txns: list[dict[str, Any]], today: date, macro: dict[str, Any] | None = None) -> dict[str, Any]:
    by_month = spend_by_month(txns)
    have = set(months_with_data(txns))
    current = ym(today)
    recent = [m for m in last_full_months(today, 3) if m in have]
    baseline = avg(by_month.get(m, 0.0) for m in recent)

    # Last year's equivalent of the baseline months (whatever exists in the data).
    ly_ref = [ym_add(m, -12) for m in recent if ym_add(m, -12) in have]
    ly_base = avg(by_month[m] for m in ly_ref) if ly_ref else 0.0

    def season(month: str) -> tuple[float, bool]:
        ly = ym_add(month, -12)
        if ly_base and ly in have:
            return by_month.get(ly, 0.0) / ly_base, True
        return 1.0, False

    # Typical swing between ordinary months (exclude December so Christmas doesn't widen everything).
    hist_months = [m for m in last_full_months(today, 12) if m in have and not m.endswith("-12")]
    swing = pstdev([by_month.get(m, 0.0) for m in hist_months]) if len(hist_months) > 2 else baseline * 0.08

    # Per-category monthly baseline, used to price announced rises (e.g. the energy cap).
    cat_month: dict[str, float] = {}
    for m in recent:
        for t in txns:
            if t["date"].startswith(m) and t["direction"] == "debit":
                cat_month[t["category"]] = cat_month.get(t["category"], 0.0) + t["amount"] / len(recent)

    actual = [
        {"month": m, "label": month_label(m), "total": round(by_month.get(m, 0.0), 2)}
        for m in last_full_months(today, HISTORY_MONTHS)
        if m in have
    ]

    forecast = []
    mtd = by_month.get(current, 0.0)
    for h in range(HORIZON + 1):
        m = ym_add(current, h)
        idx, seasonal = season(m)
        drivers: list[dict[str, Any]] = []
        expected = baseline * idx
        if seasonal and abs(idx - 1) >= 0.03:
            drivers.append({
                "label": f"Seasonal pattern: {month_label(m, False)} last year was {abs(idx - 1) * 100:.0f}% "
                + ("above" if idx > 1 else "below") + " a normal month",
                "amount": round(expected - baseline, 2),
            })
        rises = _price_rise_for_month(m, macro, cat_month)
        expected += sum(r["amount"] for r in rises)
        drivers.extend(rises)
        point: dict[str, Any] = {"month": m, "label": month_label(m)}
        if h == 0:
            # Current month: what's already spent, plus what a normal month still has to come
            # after this point (bills like rent land early, so this isn't a straight pro-rata).
            early = avg(
                spend_between(txns, date.fromisoformat(f"{pm}-01"), date.fromisoformat(f"{pm}-01") + timedelta(days=today.day - 2), None)
                for pm in recent
            ) if today.day > 1 else 0.0
            expected = mtd + max(0.0, expected - early * idx)
            point["actual_to_date"] = round(mtd, 2)
            width = swing * 0.5
        else:
            width = swing * (1 + 0.3 * (h - 1))
        point.update({
            "predicted": round(expected, 2),
            "low": round(max(0.0, expected - width), 2),
            "high": round(expected + width, 2),
            "seasonal_index": round(idx, 2),
            "drivers": drivers,
        })
        forecast.append(point)

    peak = max(forecast[1:], key=lambda p: p["predicted"]) if len(forecast) > 1 else None
    return {
        "currency": "GBP",
        "baseline_monthly": round(baseline, 2),
        "baseline_months": recent,
        "typical_swing": round(swing, 2),
        "actual": actual,
        "forecast": forecast,
        "peak": peak and {"month": peak["month"], "label": month_label(peak["month"], False),
                          "predicted": peak["predicted"], "above_baseline": round(peak["predicted"] - baseline, 2)},
        "basis": [
            f"{len(have)} months of your history",
            "Seasonal patterns from last year",
            "Announced local price changes",
            "Your recurring bills",
        ],
        "method": "Average of your last 3 months, adjusted by how the same month went last year, plus announced price rises.",
    }
