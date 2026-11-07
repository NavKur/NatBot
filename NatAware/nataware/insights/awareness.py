"""Seasonal "Awareness for you" cards: what's coming, what it cost last time, what to put aside."""

from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from statistics import pstdev
from typing import Any

from nataware.config import settings
from nataware.insights.common import days_in_month, gbp, last_full_months, spend_between

MIN_EXTRA = 10.0
WINDOW_DAYS = 120  # show what's coming in roughly the next four months


@lru_cache(maxsize=1)
def load_events() -> list[dict[str, Any]]:
    raw = json.loads((settings.config_dir / "seasonal_events.json").read_text(encoding="utf-8"))
    return raw["events"]


def _window(year: int, start_md: str, end_md: str) -> tuple[date, date]:
    sm, sd = map(int, start_md.split("-"))
    em, ed = map(int, end_md.split("-"))
    start = date(year, sm, sd)
    end_year = year + 1 if (em, ed) < (sm, sd) else year
    end = date(end_year, em, min(ed, 28 if em == 2 else ed))
    return start, end


def _next_window(today: date, ev: dict[str, Any]) -> tuple[date, date]:
    for year in (today.year - 1, today.year, today.year + 1):
        start, end = _window(year, ev["start"], ev["end"])
        if end >= today:
            return start, end
    return _window(today.year + 1, ev["start"], ev["end"])


def _minus_year(d: date) -> date:
    return d.replace(year=d.year - 1, day=min(d.day, 28)) if d.month == 2 else d.replace(year=d.year - 1)


def _area_items(macro: dict[str, Any] | None, ids: list[str]) -> list[dict[str, Any]]:
    if not macro:
        return []
    pool = [*macro.get("weather_alerts", []), *macro.get("economic_news", []), *macro.get("local_notes", [])]
    return [i for i in pool if i.get("id") in ids]


def seasonal_awareness(
    txns: list[dict[str, Any]],
    today: date,
    macro: dict[str, Any] | None,
    set_asides: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    first = min((t["date"] for t in txns), default=today.isoformat())
    normal_months = last_full_months(today, 3)
    normal_start = date.fromisoformat(f"{normal_months[0]}-01")
    normal_end = date.fromisoformat(f"{normal_months[-1]}-{days_in_month(normal_months[-1]):02d}")
    normal_days = (normal_end - normal_start).days + 1
    saved = {s["event_id"]: s for s in (set_asides or [])}

    cards = []
    for ev in load_events():
        start, end = _next_window(today, ev)
        if (start - today).days > WINDOW_DAYS:
            continue  # too far ahead to act on yet
        days = (end - start).days + 1
        ly_start, ly_end = _minus_year(start), _minus_year(end)
        full_coverage = ly_start.isoformat() >= first
        cats = ev["categories"]

        ly_spend = spend_between(txns, ly_start, ly_end, cats)
        normal_daily = spend_between(txns, normal_start, normal_end, cats) / normal_days
        history_extra = max(0.0, ly_spend - normal_daily * days)

        contributors = []
        for c in cats:
            c_extra = spend_between(txns, ly_start, ly_end, [c]) - spend_between(txns, normal_start, normal_end, [c]) / normal_days * days
            if c_extra >= 5:
                contributors.append({"category": c, "extra": round(c_extra, 2)})
        contributors.sort(key=lambda r: -r["extra"])

        area = _area_items(macro, ev.get("area_ids", []))
        price_extra = 0.0
        for item in area:
            pct = item.get("price_change_pct")
            overlap = [c for c in item.get("affects", []) if c in cats]
            if not pct or not overlap:
                continue
            item_start = max(start, date.fromisoformat(item.get("starts", start.isoformat())))
            if item_start > end:
                continue
            share = ((end - item_start).days + 1) / days
            price_extra += spend_between(txns, ly_start, ly_end, overlap) * share * pct / 100

        extra = round(history_extra + price_extra, 2)
        if extra < MIN_EXTRA:
            continue

        # Save gradually: until the end if it's already under way, otherwise until the
        # middle of the window (the costs are spread across it).
        in_progress = start <= today
        if in_progress:
            still_to_come = extra * ((end - today).days + 1) / days
            weeks = max(1.0, (end - today).days / 7)
        else:
            still_to_come = extra
            midpoint = start + (end - start) / 2
            weeks = max(1.0, (midpoint - today).days / 7)
        weekly = max(1, math.ceil(still_to_come / weeks))

        # Heuristic confidence: a full year of history, local evidence, and how regular this
        # spending normally is (steady bills are easier to predict than shopping).
        monthly = [spend_between(txns, date.fromisoformat(f"{m}-01"),
                                 date.fromisoformat(f"{m}-{days_in_month(m):02d}"), cats) for m in normal_months]
        mean_m = sum(monthly) / len(monthly) if monthly else 0
        cv = (pstdev(monthly) / mean_m) if mean_m else 1.0
        confidence = 0.5 + (0.2 if full_coverage else 0) + (0.08 if area else 0) + 0.14 * (1 - min(1.0, 2 * cv))
        confidence = min(0.95, confidence)
        impact = "high" if extra >= 100 else "medium" if extra >= 40 else "low"

        period = "December" if ev["id"] == "christmas" else f"{ly_start:%B} to {ly_end:%B}"
        history_line = (
            f"Last {period} you spent {gbp(ly_spend)} on {ev['what']}, about {gbp(history_extra)} more "
            f"than the same stretch would cost at your normal rate."
            if full_coverage and history_extra >= 1
            else "We don't have a full year of your history yet, so this leans on local patterns."
        )
        area_line = " ".join(i.get("detail") or i.get("headline", "") for i in area[:2])

        cards.append({
            "id": ev["id"],
            "title": ev["title"],
            "icon": ev["icon"],
            "window_label": ev["window_label"],
            "starts": start.isoformat(),
            "ends": end.isoformat(),
            "in_progress": in_progress,
            "expected_extra": extra,
            "still_to_come": round(still_to_come, 2),
            "history_extra": round(history_extra, 2),
            "price_extra": round(price_extra, 2),
            "last_year_spend": ly_spend,
            "contributors": contributors[:3],
            "confidence": round(confidence, 2),
            "impact": impact,
            "weekly_save": weekly,
            "weeks": round(weeks, 1),
            "why": {"history": history_line, "area": area_line},
            "area_sources": [{"id": i["id"], "headline": i["headline"]} for i in area],
            "set_aside": saved.get(ev["id"]),
        })
    return sorted(cards, key=lambda c: c["starts"])
