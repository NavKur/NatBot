"""Central configuration, loaded from environment variables / a local .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or "").strip() or default


def _bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- Real services (Phase 1 voice loop + conversational coach) ---
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    # Reasoning effort for the conversation (low | medium | high). Lower = faster spoken replies.
    anthropic_effort: str = field(default_factory=lambda: _env("ANTHROPIC_EFFORT", "medium"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "whisper-1"))
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY", ""))
    # Default voice is "Lily" (British, warm, female) from the ElevenLabs premade library.
    elevenlabs_voice_id: str = field(default_factory=lambda: _env("ELEVENLABS_VOICE_ID", "pFZP5JQG7iQjIQuC4Bku"))
    # multilingual_v2 sounds more natural; eleven_turbo_v2_5 starts speaking a little sooner.
    elevenlabs_model: str = field(default_factory=lambda: _env("ELEVENLABS_MODEL", "eleven_multilingual_v2"))

    # --- Voice activity detection ---
    vad_silence_seconds: float = field(default_factory=lambda: float(_env("VAD_SILENCE_SECONDS", "1.5")))
    vad_aggressiveness: int = field(default_factory=lambda: int(_env("VAD_AGGRESSIVENESS", "2")))

    # --- Infrastructure (faked while DEMO_MODE is on) ---
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql://nataware:nataware@localhost:5432/nataware")
    )
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0"))
    user_city: str = field(default_factory=lambda: _env("USER_CITY", "Manchester"))
    currency_symbol: str = "£"

    # The fake data set ends on 2026-11-06, so "today" is pinned for the demo to keep
    # relative questions ("last month", "this week") meaningful whenever it is run.
    demo_today: date = field(default_factory=lambda: date.fromisoformat(_env("DEMO_TODAY", "2026-11-07")))

    # --- Paths ---
    seed_dir: Path = REPO_ROOT / "data" / "seed"
    runtime_dir: Path = REPO_ROOT / "data" / "runtime"
    config_dir: Path = REPO_ROOT / "config"


settings = Settings()
