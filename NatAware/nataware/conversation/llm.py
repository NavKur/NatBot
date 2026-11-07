"""Streaming Claude conversation with an agentic tool-use loop.

Each call to `send()` streams the reply token by token. Text is pushed through a
`SpeechChunker` so complete sentences reach the `on_sentence` callback (and the TTS queue)
while Claude is still generating. If Claude calls tools, they are executed, the results
are fed back, and streaming continues until Claude produces a final answer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from nataware.config import settings
from nataware.voice.chunker import SpeechChunker

log = logging.getLogger(__name__)

SentenceCallback = Callable[[str], None]
ToolCallback = Callable[[str, dict, dict], None]
ToolExecutor = Callable[[str, dict], dict]

MAX_TOOL_ROUNDS = 8


def _noop(*_args: Any) -> None:
    return None


class ClaudeConversation:
    def __init__(
        self,
        system: str,
        tools: list[dict] | None = None,
        tool_executor: ToolExecutor | None = None,
        max_tokens: int = 1024,
    ) -> None:
        import anthropic

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.system = system
        self.tools = tools or []
        self.tool_executor = tool_executor
        self.max_tokens = max_tokens
        # The blueprint's `message_history`: alternating user / assistant turns.
        self.message_history: list[dict[str, Any]] = []

    def send(
        self,
        user_content: str,
        on_sentence: SentenceCallback = _noop,
        on_tool: ToolCallback = _noop,
    ) -> str:
        """Send a user message, stream the reply, run any tools, return the full reply text."""
        self.message_history.append({"role": "user", "content": user_content})
        text_parts: list[str] = []

        for _round in range(MAX_TOOL_ROUNDS):
            chunker = SpeechChunker()
            kwargs: dict[str, Any] = {
                "model": settings.anthropic_model,
                "max_tokens": self.max_tokens,
                "system": self.system,
                "messages": self.message_history,
            }
            if self.tools:
                kwargs["tools"] = self.tools

            with self._client.messages.stream(**kwargs) as stream:
                for delta in stream.text_stream:
                    for sentence in chunker.feed(delta):
                        on_sentence(sentence)
                final = stream.get_final_message()
            for sentence in chunker.flush():
                on_sentence(sentence)

            content = _to_param_blocks(final.content)
            if content:
                self.message_history.append({"role": "assistant", "content": content})
            text_parts.extend(b["text"] for b in content if b["type"] == "text")

            if final.stop_reason != "tool_use":
                break

            results = []
            for block in content:
                if block["type"] != "tool_use":
                    continue
                result, is_error = self._run_tool(block["name"], block["input"])
                on_tool(block["name"], block["input"], result)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result, default=str),
                        "is_error": is_error,
                    }
                )
            self.message_history.append({"role": "user", "content": results})
        else:
            log.warning("Stopped after %d tool rounds", MAX_TOOL_ROUNDS)

        return "\n".join(p for p in text_parts if p.strip())

    def _run_tool(self, name: str, tool_input: dict) -> tuple[dict, bool]:
        if self.tool_executor is None:
            return {"error": f"No tools are available (asked for {name})."}, True
        try:
            return self.tool_executor(name, tool_input), False
        except Exception as exc:  # report tool failures back to Claude instead of crashing
            log.exception("Tool %s failed", name)
            return {"error": f"{type(exc).__name__}: {exc}"}, True


def _to_param_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    """Convert SDK response blocks into plain request params for the next turn."""
    out: list[dict[str, Any]] = []
    for b in blocks:
        if b.type == "text":
            if b.text.strip():  # the API rejects empty text blocks
                out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out
