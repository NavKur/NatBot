"""Exercise the streaming tool-use loop against a fake Anthropic client (no network)."""

from types import SimpleNamespace as NS

from nataware.conversation.llm import ClaudeConversation
from nataware.conversation.tools import execute_tool


class FakeStream:
    def __init__(self, deltas, final):
        self.text_stream = iter(deltas)
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return self.scripted.pop(0)


def make_conversation(scripted):
    convo = object.__new__(ClaudeConversation)
    convo._client = NS(messages=FakeMessages(scripted))
    convo.system, convo.max_tokens = "test", 100
    convo.tools, convo.tool_executor = [{"name": "search_transactions"}], execute_tool
    convo.message_history = []
    return convo


def test_tool_round_trip_and_sentences():
    tool_call = NS(type="tool_use", id="tu_1", name="search_transactions", input={"query": "casino"})
    first = FakeStream(["Let me check. "], NS(stop_reason="tool_use", content=[NS(type="text", text="Let me check. "), tool_call]))
    second = FakeStream(["You didn't ", "spend on that. ", "Nice."],
                        NS(stop_reason="end_turn", content=[NS(type="text", text="You didn't spend on that. Nice.")]))
    convo = make_conversation([first, second])

    spoken, tools = [], []
    reply = convo.send("Did I gamble?", spoken.append, lambda n, a, r: tools.append((n, r["match_count"])))

    assert spoken == ["Let me check.", "You didn't spend on that.", "Nice."]
    assert tools == [("search_transactions", 0)]
    assert "didn't spend" in reply
    roles = [m["role"] for m in convo.message_history]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert convo.message_history[2]["content"][0]["type"] == "tool_result"
