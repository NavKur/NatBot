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
