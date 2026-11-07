"""Exogenous data aggregation -> `Daily_Macro_Summary`.

Production: a scheduled job calls the OpenWeatherMap alerts endpoint and NewsAPI (or a
scraper) for the user's coordinates and concatenates the results.

DEMO: returns the synthetic Manchester summary in `data/seed/macro_summary.json`. The
function signatures match the real version so the swap is local to this file.
"""

from __future__ import annotations

import json
from typing import Any

from nataware.config import settings


def fetch_weather_alerts(city: str) -> list[dict[str, Any]]:
    return _seed()["weather_alerts"]


def fetch_economic_news(city: str) -> list[dict[str, Any]]:
    return _seed()["economic_news"]


def build_daily_macro_summary(city: str | None = None) -> dict[str, Any]:
    city = city or settings.user_city
    return {
        "city": city,
        "date": settings.demo_today.isoformat(),
        "source": "synthetic-demo-data",
        "weather_alerts": fetch_weather_alerts(city),
        "economic_news": fetch_economic_news(city),
    }


def _seed() -> dict[str, Any]:
    return json.loads((settings.seed_dir / "macro_summary.json").read_text(encoding="utf-8"))
