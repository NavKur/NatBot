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
