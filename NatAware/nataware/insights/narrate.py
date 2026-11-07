"""Claude rewrites the computed insight facts into warm, plain-English dashboard copy.

Hybrid design: the numbers are computed deterministically (see the other modules); Claude
only writes the words. Each item is cached by a hash of its facts, so the dashboard always
renders instantly from templates and upgrades to Claude's wording once it is ready. With no
API key (or on any error) the templates are used.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from nataware.config import settings

log = logging.getLogger(__name__)

SYSTEM = """\
You write the short insight text on NatAware, a money coaching app for people of all
backgrounds, including people on low incomes, people with low confidence with money, and
people for whom English is a second language. NatBot is the app's friendly coach.

For every item you receive, write two versions:
- plain: one sentence, at most 22 words, reading age about 9. Everyday words, no jargon,
  no acronyms. Lead with what it means for the person.
- detail: at most 45 words. Can include the key numbers and why NatBot thinks this.

Rules:
- Use ONLY the facts given. Never invent numbers, merchants, dates or places.
- Money as £ with whole pounds unless pennies matter (e.g. a £8.99 subscription).
- Warm, direct and non-judgemental. Never shame. No exclamation marks, no emoji.
- Do not give regulated financial advice or recommend specific investment products.
- Return every item id you were given, unchanged."""


class NarratedItem(BaseModel):
    id: str
    plain: str
    detail: str


class Narration(BaseModel):
    items: list[NarratedItem]


def _key(item: dict[str, Any]) -> str:
    payload = json.dumps({k: item.get(k) for k in ("id", "facts", "plain", "detail")}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


class Narrator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self.last_error: str | None = None

    def apply(self, items: list[dict[str, Any]], cache: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (items with cached wording applied, items still missing wording)."""
        out, missing = [], []
        for item in items:
            hit = cache.get(_key(item))
            if hit:
                out.append({**item, "plain": hit["plain"], "detail": hit["detail"], "narrated": True})
            else:
                out.append({**item, "narrated": False})
                missing.append(item)
        return out, missing

    @property
    def running(self) -> bool:
        return self._running

    def ensure(self, missing: list[dict[str, Any]], context: dict[str, Any], on_done) -> str:
        """Start background narration for missing items. Returns a status string."""
        if not missing:
            return "ready"
        if not settings.anthropic_api_key:
            return "templates"
        with self._lock:
            if self._running:
                return "pending"
            self._running = True
        threading.Thread(target=self._run, args=(missing, context, on_done), name="nataware-narrate", daemon=True).start()
        return "pending"

    def _run(self, missing: list[dict[str, Any]], context: dict[str, Any], on_done) -> None:
        try:
            results = narrate(missing, context)
            on_done({_key(i): results[i["id"]] for i in missing if i["id"] in results})
            self.last_error = None
        except Exception as exc:  # never break the dashboard over wording
            log.exception("Narration failed")
            self.last_error = f"{type(exc).__name__}: {exc}"
        finally:
            with self._lock:
                self._running = False


def narrate(items: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, dict[str, str]]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = {
        "person": context,
        "items": [
            {"id": i["id"], "kind": i.get("kind"), "facts": i.get("facts", {}),
             "draft_plain": i.get("plain"), "draft_detail": i.get("detail")}
            for i in items
        ],
    }
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=SYSTEM,
        output_config={"effort": "low"},
        output_format=Narration,
        messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise RuntimeError(f"Narration stopped early: {response.stop_reason}")
    wanted = {i["id"] for i in items}
    return {
        n.id: {"plain": n.plain.strip(), "detail": n.detail.strip(), "at": datetime.now().isoformat(timespec="seconds")}
        for n in response.parsed_output.items
        if n.id in wanted and n.plain.strip()
    }


narrator = Narrator()
