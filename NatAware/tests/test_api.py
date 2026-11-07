from fastapi.testclient import TestClient

from nataware.api.main import app
from nataware.config import settings


def client():
    return TestClient(app)


def test_read_endpoints():
    with client() as c:
        assert c.get("/health").json()["agent"] == "NatBot"
        assert c.get("/profile").json()["tendency"] == "The Comfort-Buyer"
        alcohol = c.get("/transactions", params={"category": "Alcohol & Nightlife"}).json()
        assert alcohol["count"] > 0
        assert c.get("/transactions", params={"flagged_only": True}).json()["count"] > 0
        assert c.get("/budget").json()["month"] == "2026-10"
        assert c.get("/threats").json()["threats"]
        assert c.get("/coaching/plan").json()["weekly_limit"] > 0


def test_triggers_and_nudges():
    with client() as c:
        for kind in ("transaction", "macro", "temporal"):
            r = c.post(f"/triggers/{kind}")
            assert r.status_code == 200, r.text
            assert r.json()["trigger"] == kind
        assert len(c.get("/nudges").json()["nudges"]) >= 3


def test_statement_upload():
    with client() as c, open(settings.seed_dir / "sample_statement.csv", "rb") as f:
        r = c.post("/statements/upload", files={"file": ("statement.csv", f, "text/csv")})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["added"] == 6
    cats = {t["merchant"]: t["category"] for t in body["transactions"]}
    assert cats["DELIVEROO"] == "Takeaway & Delivery"
    assert cats["THE PILCROW PUB"] == "Alcohol & Nightlife"


def test_add_transaction_validates_category():
    with client() as c:
        assert c.post("/transactions", json={"merchant": "X", "amount": 5, "category": "Nope"}).status_code == 422
        ok = c.post("/transactions", json={"merchant": "Just Eat", "amount": 18, "category": "Takeaway & Delivery", "time": "21:30"})
        assert ok.json()["transaction"]["is_flagged"]


def test_first_run_state_and_skip():
    with client() as c:
        state = c.get("/app/state").json()
        assert state["onboarded"] is False and state["account"]["first_name"] == "Alex"
        assert c.post("/onboarding/skip").json()["onboarded"] is True


def test_dashboard_payload():
    with client() as c:
        d = c.get("/dashboard").json()
    assert d["goals"]["goals"] and d["forecast"]["forecast"] and d["awareness"] and d["noticed"]
    assert d["stats"]["committed"]["count"] > 0
    assert all(card["plain"] and card["detail"] for card in d["noticed"])


def test_set_asides_feed_the_winter_buffer():
    with client() as c:
        assert c.post("/setasides", json={"event_id": "heating", "weekly": 12}).status_code == 200
        assert c.get("/dashboard").json()["stats"]["winter_buffer"]["weekly"] == 12
        assert c.post("/setasides", json={"event_id": "nope", "weekly": 5}).status_code == 404
        c.delete("/setasides/heating")
        assert c.get("/dashboard").json()["stats"]["winter_buffer"]["weekly"] == 0


def _events(text):
    import json as _json

    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], _json.loads(lines["data"])))
    return out


def test_chat_stream_emits_sentences_tools_and_done(monkeypatch):
    """The SSE contract the web app depends on, with a fake coach (no network)."""
    from nataware.api import main as api_main
    from nataware.conversation import sessions

    class FakeCoach:
        def __init__(self):
            self.message_history = []

        def reply(self, text, on_sentence, on_tool):
            on_sentence("Let me look.")
            on_tool("search_transactions", {"query": "pub"}, {"match_count": 3})
            on_sentence("Three pub visits.")
            return "Let me look. Three pub visits."

    from dataclasses import replace

    monkeypatch.setattr(api_main, "settings", replace(api_main.settings, anthropic_api_key="test-key"))
    monkeypatch.setattr(sessions, "CoachSession", FakeCoach)
    with client() as c:
        r = c.post("/chat/stream", json={"message": "pubs?", "mode": "coach"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    assert [e for e, _ in events] == ["session", "sentence", "tool", "sentence", "done"]
    assert events[2][1]["result"]["match_count"] == 3
    assert events[-1][1]["reply"] == "Let me look. Three pub visits."


def test_voice_endpoints_report_missing_keys(monkeypatch):
    from nataware.api import main as api_main

    from dataclasses import replace

    monkeypatch.setattr(api_main, "settings", replace(api_main.settings, openai_api_key="", elevenlabs_api_key=""))
    with client() as c:
        assert c.post("/voice/speak", json={"text": "hi"}).status_code == 503
        assert c.post("/voice/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}).status_code == 503
