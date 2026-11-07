"""Transition-matrix lookups, event triggers and intervention (nudge) generation.

Production: the triggered Celery task prompts Claude with the trigger context, current
micro-goal and recent highlighted transactions to write a personalised nudge.

DEMO: nudges come from templates (`generate_nudge`) with the same output shape;
`build_intervention_prompt` shows what would be sent to Claude.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from nataware.config import settings
from nataware.data import queries as q
from nataware.profile import Profile

TRIGGERS = ("transaction", "macro", "temporal")


@lru_cache(maxsize=1)
def load_transition_matrix() -> dict[str, Any]:
    return json.loads((settings.config_dir / "transition_matrix.json").read_text(encoding="utf-8"))


def current_plan(profile: Profile | None, txns: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    if profile is None:
        return {"error": "No profile yet - complete onboarding first."}
    today = today or settings.demo_today
    matrix = load_transition_matrix()
    tconf = matrix["tendencies"][profile.tendency.value]
    stages = matrix["capacities"][profile.capacity.value]["stages"]

    assessed = q.to_date(profile.assessed_at) or today
    weeks_in = max(0, (today - assessed).days // 7)
    stage_idx, cumulative = len(stages) - 1, 0
    for i, s in enumerate(stages):
        cumulative += s["weeks"]
        if weeks_in < cumulative:
            stage_idx = i
            break
    stage = stages[stage_idx]

    weekly_limit = round(tconf["starting_weekly_limit"] * stage["limit_multiplier"])
    week_start, week_end = q.week_bounds(today)
    this_week = q.filter_transactions(
        txns, categories=tconf["watch_categories"], date_from=week_start, date_to=week_end
    )
    spent = round(sum(t["amount"] for t in this_week), 2)

    return {
        "profile": profile.label,
        "weeks_since_onboarding": weeks_in,
        "stage": {"number": stage_idx + 1, "of": len(stages), "id": stage["id"], "name": stage["name"]},
        "micro_goals": stage["micro_goals"],
        "habit_swap": tconf["habit_swap"],
        "watch_categories": tconf["watch_categories"],
        "week": {"start": week_start.isoformat(), "end": week_end.isoformat()},
        "weekly_limit": weekly_limit,
        "spent_this_week": spent,
        "remaining_this_week": round(weekly_limit - spent, 2),
        "over_limit": spent > weekly_limit,
        "optimal_baseline": profile.optimal_baseline.model_dump(),
        "next_stage": stages[stage_idx + 1]["name"] if stage_idx + 1 < len(stages) else None,
    }


# ---------------------------------------------------------------------- triggers
def transaction_trigger_fires(txn: dict[str, Any], plan: dict[str, Any]) -> bool:
    """A new flagged transaction pushed the watched categories over this week's micro-goal limit."""
    return bool(
        txn.get("is_flagged")
        and txn["category"] in plan.get("watch_categories", [])
        and plan.get("over_limit")
    )


def temporal_trigger_due(now: datetime) -> bool:
    """Friday 16:00 weekend-prep nudge (Celery beat runs this on a crontab)."""
    return now.weekday() == 4 and now.hour == 16


# ---------------------------------------------------------------------- nudges
def generate_nudge(trigger: str, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if trigger not in TRIGGERS:
        raise ValueError(f"Unknown trigger {trigger!r}; expected one of {TRIGGERS}")
    limit, spent = plan.get("weekly_limit", 0), plan.get("spent_this_week", 0)

    if trigger == "transaction":
        t = context["transaction"]
        title = "That one tipped you over"
        message = (
            f"£{t['amount']:.2f} at {t['merchant']} puts you at £{spent:.0f} against your £{limit} weekly "
            f"limit. {plan.get('habit_swap', '')} Want me to move £10 into savings to balance it?"
        )
        channel = "push"
    elif trigger == "macro":
        th = context["threat"]
        title = f"Heads up: {th['threat_name']}"
        message = (
            f"This could cost you about £{th['estimated_dollar_burden']:.0f}. {th['recommended_budget_shift']} "
            "Doing it now means it won't feel like a shock later."
        )
        channel = "push"
    else:
        remaining = plan.get("remaining_this_week", 0)
        title = "Weekend game plan"
        message = (
            f"It's Friday. You've got £{max(remaining, 0):.0f} left in your watch budget for the weekend"
            + ("" if remaining > 0 else " - you're already over, so tonight's a free-plans night")
            + f". This stage's goal: {plan.get('micro_goals', [''])[0]}."
        )
        channel = "audio"  # queued ElevenLabs voice note in production

    return {
        "id": f"ndg_{uuid.uuid4().hex[:8]}",
        "trigger": trigger,
        "title": title,
        "message": message,
        "channel": channel,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stage": plan.get("stage", {}).get("name"),
    }


def build_intervention_prompt(trigger: str, context: dict[str, Any], plan: dict[str, Any], recent: list[dict]) -> str:
    """The prompt the production nudge generator would send to Claude. Not called in the demo."""
    return (
        f"Trigger: {trigger}\nContext: {json.dumps(context, default=str)}\n"
        f"Current plan and micro-goal: {json.dumps(plan)}\n"
        f"Recent highlighted transactions: {json.dumps(recent[:10])}\n\n"
        "Write one short, warm, specific behavioural nudge (max 40 words) that redirects the user "
        "towards their optimal baseline. Return JSON: {\"title\": str, \"message\": str}."
    )
