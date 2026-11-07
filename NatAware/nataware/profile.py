"""The 2D psych-profile matrix (Capacity x Tendency) and helpers to extract it from LLM output."""

from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Capacity(str, Enum):
    OVER_LEVERAGED = "The Over-Leveraged"
    SCRAPPER = "The Scrapper"
    STABILIZER = "The Stabilizer"
    ACCUMULATOR = "The Accumulator"


class Tendency(str, Enum):
    COMFORT_BUYER = "The Comfort-Buyer"
    STATUS_SEEKER = "The Status-Seeker"
    EXPERIENCE_JUNKIE = "The Experience-Junkie"
    PANIC_HOARDER = "The Panic-Hoarder"


class OptimalBaseline(BaseModel):
    needs: float = Field(ge=0, le=100)
    wants: float = Field(ge=0, le=100)
    savings: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _normalise(self) -> "OptimalBaseline":
        """LLMs occasionally return splits that don't sum to exactly 100; rescale them."""
        total = self.needs + self.wants + self.savings
        if total <= 0:
            raise ValueError("baseline split must be positive")
        if abs(total - 100) > 0.01:
            self.needs = round(self.needs * 100 / total, 1)
            self.wants = round(self.wants * 100 / total, 1)
            self.savings = round(100 - self.needs - self.wants, 1)
        return self


class Profile(BaseModel):
    capacity: Capacity
    tendency: Tendency
    optimal_baseline: OptimalBaseline
    rationale: str = ""
    assessed_at: str | None = None  # ISO date the onboarding interview finished

    @property
    def label(self) -> str:
        return f"{self.capacity.value} {self.tendency.value.removeprefix('The ')}"


PROFILE_OPEN = "<profile>"
_PROFILE_RE = re.compile(r"<profile>\s*(.*?)\s*</profile>", re.DOTALL | re.IGNORECASE)
# Also strips an unterminated block (e.g. if the model is cut off mid-JSON).
_STRIP_RE = re.compile(r"<profile>.*?(?:</profile>|$)", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def extract_profile(text: str) -> Profile | None:
    """Return the Profile embedded in `<profile>` tags, or None if absent / invalid."""
    match = _PROFILE_RE.search(text)
    if not match:
        return None
    raw = _FENCE_RE.sub("", match.group(1).strip())
    try:
        return Profile.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def strip_profile(text: str) -> str:
    """Remove the hidden profile block so it is never spoken or shown."""
    return _STRIP_RE.sub("", text).strip()
