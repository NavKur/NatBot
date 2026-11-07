"""The two conversation modes, shared by the voice CLI and the HTTP API.

* `OnboardingSession` - the 3-question psych-profiling state machine (Phase 1).
* `CoachSession`      - open conversation where NatBot answers questions about the user's
                        (fake) data using tools.
"""

from __future__ import annotations

from typing import Callable

from nataware import AGENT_NAME
from nataware.config import settings
from nataware.conversation.llm import ClaudeConversation, SentenceCallback, ToolCallback, _noop
from nataware.conversation.prompts import (
    ONBOARDING_KICKOFF,
    ONBOARDING_SYSTEM_PROMPT,
    ONBOARDING_WRAP_UP_NUDGE,
    coach_system_prompt,
)
from nataware.conversation.tools import TOOL_DEFINITIONS, execute_tool
from nataware.data.store import get_store
from nataware.profile import Profile, extract_profile, strip_profile

QUESTIONS = 3


class OnboardingSession:
    def __init__(self, on_profile: Callable[[Profile], None] | None = None) -> None:
        self.convo = ClaudeConversation(system=ONBOARDING_SYSTEM_PROMPT, max_tokens=800)
        self.profile: Profile | None = None
        self.answers = 0
        self._on_profile = on_profile or save_profile

    @property
    def message_history(self) -> list[dict]:
        return self.convo.message_history

    def start(self, on_sentence: SentenceCallback = _noop) -> str:
        return self._handle(self.convo.send(ONBOARDING_KICKOFF, on_sentence))

    def reply(self, user_text: str, on_sentence: SentenceCallback = _noop) -> str:
        self.answers += 1
        content = user_text
        if self.answers > QUESTIONS:
            # Safety net: if the model is still asking (e.g. it re-asked a vague answer),
            # remind it to wrap up rather than let the interview drift.
            content += ONBOARDING_WRAP_UP_NUDGE.format(agent=AGENT_NAME)
        return self._handle(self.convo.send(content, on_sentence))

    def _handle(self, raw: str) -> str:
        profile = extract_profile(raw)
        if profile:
            profile.assessed_at = settings.demo_today.isoformat()
            self.profile = profile
            self._on_profile(profile)
        return strip_profile(raw)


class CoachSession:
    def __init__(self) -> None:
        store = get_store()
        profile = store.get_profile()
        if profile is None:
            raise RuntimeError("No profile yet - run onboarding first.")
        dates = sorted(t["date"] for t in store.transactions)
        self.convo = ClaudeConversation(
            system=coach_system_prompt(profile, dates[0], dates[-1], (store.get("account") or {}).get("first_name")),
            tools=TOOL_DEFINITIONS,
            tool_executor=execute_tool,
            max_tokens=1200,
        )

    @property
    def message_history(self) -> list[dict]:
        return self.convo.message_history

    def reply(self, user_text: str, on_sentence: SentenceCallback = _noop, on_tool: ToolCallback = _noop) -> str:
        return self.convo.send(user_text, on_sentence, on_tool)


def save_profile(profile: Profile) -> None:
    """Persist a new profile and re-run the downstream (fake) pipelines that depend on it."""
    from nataware.worker.tasks import refresh_threats, retag_all_transactions

    store = get_store()
    store.set_profile(profile)
    store.put("onboarded", True)
    retag_all_transactions.delay()
    refresh_threats.delay()
