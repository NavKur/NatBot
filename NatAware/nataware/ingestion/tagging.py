"""Behavioural tagging: map transactions onto the user's psychological Tendency.

The blueprint sends batches of 50 untagged transactions to Claude with the user's
Tendency and gets back `[{"id", "is_flagged", "highlight_reason"}]`.

DEMO: `tag_batch()` returns exactly that contract from deterministic rules, so the demo is
fast, free and repeatable. `build_tagging_prompt()` is the prompt the production version
would send; swap `tag_batch` for an LLM call and nothing downstream changes.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from nataware.profile import Tendency

BATCH_SIZE = 50

Rule = Callable[[dict[str, Any]], str | None]


def _hour(t: dict[str, Any]) -> int | None:
    return int(t["time"][:2]) if t.get("time") else None


def _late(t: dict[str, Any]) -> bool:
    h = _hour(t)
    return h is not None and (h >= 22 or h < 3)


def _when(t: dict[str, Any]) -> str:
    return f"at {t['time']}" if t.get("time") else "that day"


def _comfort(t: dict[str, Any]) -> str | None:
    c, amt = t["category"], t["amount"]
    if c == "Takeaway & Delivery" and (_late(t) or (_hour(t) or 0) >= 20 or amt >= 25):
        return f"Delivery order {_when(t)} - convenience food as a tired or low-mood fix."
    if c == "Shopping - Online" and _late(t):
        return f"Online purchase {_when(t)} - the late-night retail-therapy window."
    if c == "Subscriptions" and t["merchant"] in {"Disney+", "Audible"}:
        return "Overlapping media subscription kept running for comfort rather than use."
    if c == "Transport" and t["merchant"].startswith("Uber") and _late(t):
        return "Late-night Uber - paying for comfort after a night out instead of the tram."
    return None


def _status(t: dict[str, Any]) -> str | None:
    c, amt = t["category"], t["amount"]
    if c == "Shopping - Clothing" and amt >= 30:
        return f"£{amt:.0f} on clothes at {t['merchant']} - image-driven purchase."
    if c == "Eating Out" and amt >= 25:
        return "Pricey meal out - spending to keep up socially."
    if c in {"Entertainment", "Travel"} and amt >= 60:
        return "Big-ticket experience - worth checking it was for you, not the group chat."
    return None


def _experience(t: dict[str, Any]) -> str | None:
    c, amt = t["category"], t["amount"]
    if c == "Alcohol & Nightlife" and (amt >= 15 or _late(t)):
        return f"Night-out spend {_when(t)} - experience spending that adds up fast."
    if c in {"Travel", "Entertainment"} and amt >= 30:
        return "Experience purchase - fine in the plan, risky outside it."
    if c == "Takeaway & Delivery" and _late(t):
        return "Post-night-out takeaway - the hidden cost of the experience."
    return None


def _panic(t: dict[str, Any]) -> str | None:
    c, amt = t["category"], t["amount"]
    if c == "Cash Withdrawal":
        return "Cash pulled out 'just in case' - money parked where it can't work."
    if c == "Groceries" and amt >= 60:
        return "Large stock-up shop - possible anxiety-driven bulk buying."
    return None


TENDENCY_RULES: dict[Tendency, Rule] = {
    Tendency.COMFORT_BUYER: _comfort,
    Tendency.STATUS_SEEKER: _status,
    Tendency.EXPERIENCE_JUNKIE: _experience,
    Tendency.PANIC_HOARDER: _panic,
}


def tag_batch(batch: list[dict[str, Any]], tendency: Tendency) -> list[dict[str, Any]]:
    rule = TENDENCY_RULES[tendency]
    results = []
    for t in batch:
        reason = rule(t) if t["direction"] == "debit" else None
        results.append({"id": t["id"], "is_flagged": reason is not None, "highlight_reason": reason})
    return results


def build_tagging_prompt(batch: list[dict[str, Any]], tendency: Tendency) -> str:
    """The prompt the production (LLM) tagger would send. Not called in the demo."""
    rows = [
        {k: t.get(k) for k in ("id", "date", "time", "merchant", "amount", "category")} for t in batch
    ]
    return (
        f"The user's spending tendency is {tendency.value}.\n"
        "For each transaction, decide whether it reflects that psychological weakness.\n"
        'Return ONLY a JSON array of {"id": str, "is_flagged": bool, "highlight_reason": str|null}.\n'
        "highlight_reason must be one short sentence linking the purchase to the tendency.\n\n"
        f"Transactions:\n{json.dumps(rows, indent=1)}"
    )
