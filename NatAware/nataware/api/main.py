"""NatAware REST API.

    uvicorn nataware.api.main:app --reload

Interactive docs at http://127.0.0.1:8000/docs. Everything except `/chat` reads the fake
demo data. `/chat` talks to the real Claude (text in / text out) and returns the tool
results NatBot used, so a front end can render highlights alongside the reply.
"""

from __future__ import annotations

import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nataware import AGENT_NAME, __version__
from nataware.coaching.engine import current_plan
from nataware.config import settings
from nataware.data import queries as q
from nataware.data.store import get_store
from nataware.worker import tasks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks.bootstrap()
    yield


app = FastAPI(title="NatAware API", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------- meta
@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": AGENT_NAME, "demo_mode": settings.demo_mode, "today": settings.demo_today}


@app.post("/demo/reset")
def demo_reset() -> dict[str, str]:
    get_store().reset()
    tasks.bootstrap()
    _sessions.clear()
    return {"status": "reset"}


# ---------------------------------------------------------------------- Phase 1 output
@app.get("/profile")
def get_profile() -> dict[str, Any]:
    profile = get_store().get_profile()
    if profile is None:
        raise HTTPException(404, "No profile yet")
    return profile.model_dump(mode="json")


# ---------------------------------------------------------------------- Phase 2
@app.get("/transactions")
def list_transactions(
    query: str | None = None,
    category: list[str] | None = Query(None),
    date_from: str | None = None,
    date_to: str | None = None,
    flagged_only: bool = False,
    direction: Literal["debit", "credit", "all"] = "all",
) -> dict[str, Any]:
    txns = q.filter_transactions(
        get_store().transactions,
        query=query,
        categories=category,
        date_from=date_from,
        date_to=date_to,
        flagged_only=flagged_only,
        direction=None if direction == "all" else direction,
    )
    return {"count": len(txns), "transactions": [q.public_view(t) for t in txns]}


@app.get("/highlights")
def list_highlights() -> dict[str, Any]:
    store = get_store()
    out = []
    for h in store.get("highlights") or []:
        txns = [store.get_transaction(i) for i in h["transaction_ids"]]
        out.append({**h, "transactions": [q.public_view(t) for t in txns if t]})
    return {"highlights": list(reversed(out))}


@app.post("/statements/upload")
async def upload_statement(file: UploadFile = File(...)) -> dict[str, Any]:
    from nataware.ingestion.parser import parse_csv, parse_pdf

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".pdf"}:
        raise HTTPException(400, "Upload a .csv or .pdf statement")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
    try:
        rows = parse_csv(tmp.name) if suffix == ".csv" else parse_pdf(tmp.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return tasks.ingest_statement.delay(rows).get()


@app.post("/tagging/run")
def run_tagging(retag_all: bool = False) -> dict[str, int]:
    task = tasks.retag_all_transactions if retag_all else tasks.tag_untagged_transactions
    return {"tagged": task.delay().get()}


@app.get("/spending/summary")
def spending_summary(
    group_by: Literal["category", "merchant", "month", "bucket"] = "category",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    txns = q.filter_transactions(get_store().transactions, date_from=date_from, date_to=date_to)
    return {"group_by": group_by, "rows": q.summarise(txns, group_by)}


@app.get("/budget")
def budget(month: str | None = None) -> dict[str, Any]:
    store = get_store()
    profile = store.get_profile()
    if profile is None:
        raise HTTPException(404, "No profile yet")
    return q.budget_status(store.transactions, profile.optimal_baseline.model_dump(), month)


# ---------------------------------------------------------------------- Phase 3
@app.get("/threats")
def list_threats() -> dict[str, Any]:
    store = get_store()
    return {"macro_summary": store.get("macro_summary"), "threats": store.get("active_threats") or []}


@app.post("/threats/refresh")
def refresh_threats() -> dict[str, Any]:
    return {"threats": tasks.refresh_threats.delay().get()}


# ---------------------------------------------------------------------- Phase 4
@app.get("/coaching/plan")
def coaching_plan() -> dict[str, Any]:
    store = get_store()
    return current_plan(store.get_profile(), store.transactions)


@app.get("/nudges")
def list_nudges(limit: int = 20) -> dict[str, Any]:
    return {"nudges": list(reversed(get_store().get("nudges") or []))[:limit]}


@app.post("/triggers/{kind}")
def fire_trigger(kind: Literal["transaction", "macro", "temporal"]) -> dict[str, Any]:
    try:
        return tasks.generate_intervention.delay(kind).get()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


class NewTransaction(BaseModel):
    merchant: str
    amount: float
    category: str
    date: str | None = None
    time: str | None = None


@app.post("/transactions")
def add_transaction(body: NewTransaction) -> dict[str, Any]:
    """Webhook-style single transaction: stored, tagged and checked against the transaction trigger."""
    if body.category not in q.CATEGORIES:
        raise HTTPException(422, f"Unknown category. Use one of: {list(q.CATEGORIES)}")
    txn = {
        "date": body.date or settings.demo_today.isoformat(),
        "time": body.time,
        "merchant": body.merchant,
        "amount": round(body.amount, 2),
        "currency": "GBP",
        "direction": "credit" if body.category == "Income" else "debit",
        "category": body.category,
        "tags": [],
        "source": "api",
    }
    return tasks.ingest_transaction.delay(txn).get()


# ---------------------------------------------------------------------- real Claude chat (text)
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    mode: Literal["coach", "onboarding"] = "coach"


_sessions: dict[str, Any] = {}


@app.post("/chat")
def chat(body: ChatRequest) -> dict[str, Any]:
    """Text chat with NatBot. Start onboarding with mode='onboarding' and an empty message."""
    from nataware.conversation.sessions import CoachSession, OnboardingSession

    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured")

    session_id = body.session_id or uuid.uuid4().hex
    session = _sessions.get(session_id)
    if session is None:
        session = OnboardingSession() if body.mode == "onboarding" else CoachSession()
        _sessions[session_id] = session

    tool_events: list[dict[str, Any]] = []

    def on_tool(name: str, args: dict, result: dict) -> None:
        tool_events.append({"tool": name, "input": args, "result": result})

    if isinstance(session, OnboardingSession):
        reply = session.reply(body.message) if session.message_history else session.start()
        profile = session.profile.model_dump(mode="json") if session.profile else None
        return {"session_id": session_id, "mode": "onboarding", "reply": reply, "profile": profile, "complete": profile is not None}

    reply = session.reply(body.message, on_tool=on_tool)
    return {"session_id": session_id, "mode": "coach", "reply": reply, "tool_events": tool_events}
