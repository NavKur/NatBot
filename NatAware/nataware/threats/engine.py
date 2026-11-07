"""Threat matrix calculation.

Production: prompt Claude with [Capacity] + [Tendency] + [Daily_Macro_Summary] +
[Current Budget State] and parse a strict JSON array of threats.

DEMO: deterministic scoring with the same output contract:
`{threat_id, threat_name, estimated_dollar_burden, currency, priority, recommended_budget_shift, ...}`.
(`estimated_dollar_burden` keeps the blueprint's field name; values are in GBP.)
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from nataware.coaching.engine import load_transition_matrix
from nataware.insights.common import friendly
from nataware.profile import Capacity, Profile

# How hard a shock lands, by financial resilience.
CAPACITY_MULTIPLIER = {
    Capacity.OVER_LEVERAGED: 1.5,
    Capacity.SCRAPPER: 1.25,
    Capacity.STABILIZER: 1.0,
    Capacity.ACCUMULATOR: 0.7,
}
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


def calculate_threats(profile: Profile, macro: dict[str, Any], budget: dict[str, Any]) -> list[dict[str, Any]]:
    multiplier = CAPACITY_MULTIPLIER[profile.capacity]
    watch = load_transition_matrix()["tendencies"][profile.tendency.value]["watch_categories"]
    source_category = watch[0]
    # Users with no slack in their budget feel every shock harder.
    no_slack = budget.get("unallocated", 0) <= 0

    threats = []
    for item in [*macro.get("weather_alerts", []), *macro.get("economic_news", [])]:
        burden = round(item["base_monthly_impact"] * multiplier, 2)
        if item["kind"] in profile_tendency_amplifiers(profile):
            burden = round(burden * 1.2, 2)
        rank = SEVERITY_RANK[item["severity"]]
        if rank < 3 and (burden >= 100 or (no_slack and burden >= 50)):
            rank += 1
        priority = {1: "low", 2: "medium", 3: "high"}[rank]
        shift = round(burden / max(item.get("months", 1), 1), 0)
        threats.append(
            {
                "threat_id": item["id"],
                "threat_name": item["headline"],
                "detail": item["detail"],
                "kind": item["kind"],
                "starts": item.get("starts"),
                "estimated_dollar_burden": burden,
                "currency": "GBP",
                "priority": priority,
                "affected_categories": item.get("affects", []),
                "recommended_budget_shift": (
                    f"Move £{shift:.0f} a month from {friendly(source_category)} into {item.get('buffer', 'bills')}"
                    f" before {_nice_date(item.get('starts'))}."
                    if item.get("starts", "") > macro.get("date", "")
                    else f"Move £{shift:.0f} from {friendly(source_category)} into {item.get('buffer', 'bills')} this month."
                ),
            }
        )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(threats, key=lambda t: (order[t["priority"]], -t["estimated_dollar_burden"]))


def _nice_date(iso: str | None) -> str:
    if not iso:
        return "it hits"
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%B}"


def profile_tendency_amplifiers(profile: Profile) -> set[str]:
    """Threat kinds that hit harder because of the user's tendency."""
    return {
        "The Comfort-Buyer": {"weather", "energy"},  # cold, dark evenings drive delivery orders
        "The Status-Seeker": {"prices"},
        "The Experience-Junkie": {"transport", "prices"},
        "The Panic-Hoarder": {"rates", "energy"},
    }.get(profile.tendency.value, set())


def build_threat_prompt(profile: Profile, macro: dict[str, Any], budget: dict[str, Any]) -> str:
    """The prompt the production (LLM) engine would send. Not called in the demo."""
    return (
        f"User capacity: {profile.capacity.value}\nUser tendency: {profile.tendency.value}\n"
        f"Daily_Macro_Summary: {json.dumps(macro)}\nCurrent budget state: {json.dumps(budget)}\n\n"
        "Return ONLY a JSON array of impending financial threats, each with threat_name, "
        "estimated_dollar_burden (number, GBP) and recommended_budget_shift (one sentence)."
    )
