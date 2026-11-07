"""Turns a streaming LLM response into speakable sentences.

* Emits text only at sentence boundaries, so TTS gets natural prosody.
* Never emits anything from the hidden `<profile>` block onwards - including when the
  opening tag arrives split across several stream deltas (e.g. "<pro" + "file>").
"""

from __future__ import annotations

import re

from nataware.profile import PROFILE_OPEN

# A sentence ends with . ! or ? (optionally followed by closing quotes/brackets) then whitespace.
# A full stop between two digits ("£12.99") is not followed by whitespace, so it never matches.
_BOUNDARY = re.compile(r"[.!?][\"')\]]*\s+")


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        parts.append(text[start : m.end()].strip())
        start = m.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def _partial_tag_len(buf: str, tag: str) -> int:
    """Length of the longest suffix of `buf` that is a proper prefix of `tag`."""
    lower = buf.lower()
    for n in range(min(len(tag) - 1, len(buf)), 0, -1):
        if lower.endswith(tag[:n]):
            return n
    return 0


class SpeechChunker:
    def __init__(self) -> None:
        self._buf = ""
        self._muted = False

    @property
    def muted(self) -> bool:
        return self._muted

    def feed(self, delta: str) -> list[str]:
        """Add a stream delta; return any sentences that are now complete and speakable."""
        if self._muted:
            return []
        self._buf += delta

        tag_at = self._buf.lower().find(PROFILE_OPEN)
        if tag_at != -1:
            speakable, self._buf = self._buf[:tag_at], ""
            self._muted = True
            return split_sentences(speakable)

        hold = _partial_tag_len(self._buf, PROFILE_OPEN)
        safe = self._buf[: len(self._buf) - hold] if hold else self._buf

        last_end = None
        for m in _BOUNDARY.finditer(safe):
            last_end = m.end()
        if last_end is None:
            return []

        ready, self._buf = self._buf[:last_end], self._buf[last_end:]
        return split_sentences(ready)

    def flush(self) -> list[str]:
        """Call when the stream ends to release any trailing text."""
        if self._muted:
            return []
        rest, self._buf = self._buf, ""
        if _partial_tag_len(rest, PROFILE_OPEN):
            rest = rest[: rest.lower().rfind("<")]
        return split_sentences(rest)
