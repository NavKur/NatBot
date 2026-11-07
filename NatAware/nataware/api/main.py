"""NatAware REST API.

    uvicorn nataware.api.main:app --reload

Interactive docs at http://127.0.0.1:8000/docs. Everything except `/chat` reads the fake
demo data. `/chat` talks to the real Claude (text in / text out) and returns the tool
results NatBot used, so a front end can render highlights alongside the reply.
"""

from __future__ import annotations

import json
import queue
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
def _capabilities() -> dict[str, bool]:
    return {
        "chat": bool(settings.anthropic_api_key),
        "speech_to_text": bool(settings.openai_api_key),
        "text_to_speech": bool(settings.elevenlabs_api_key),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": AGENT_NAME, "demo_mode": settings.demo_mode, "today": settings.demo_today,
            "capabilities": _capabilities()}


@app.get("/app/state")
def app_state() -> dict[str, Any]:
    """What the front end needs on load: is this a first visit, who is the user, what's switched on."""
    store = get_store()
    account = store.get("account") or {}
    profile = store.get_profile()
    return {
        "agent": AGENT_NAME,
        "onboarded": bool(store.get("onboarded")) and profile is not None,
        "account": {k: account.get(k) for k in ("display_name", "first_name", "account_type", "city")},
        "today": settings.demo_today.isoformat(),
        "capabilities": _capabilities(),
    }


@app.post("/onboarding/skip")
def skip_onboarding() -> dict[str, Any]:
    """Use the pre-loaded demo profile (for demos without a microphone or API keys)."""
    store = get_store()
    if store.get_profile() is None:
        raise HTTPException(409, "No demo profile available")
    store.put("onboarded", True)
    return app_state()


@app.post("/demo/reset")
def demo_reset() -> dict[str, str]:
    get_store().reset()
    tasks.bootstrap()
    _sessions.clear()
    return {"status": "reset"}


# ---------------------------------------------------------------------- dashboard ("financial time travel")
@app.get("/dashboard")
def dashboard() -> dict[str, Any]:
    from nataware.insights.dashboard import build_dashboard

    result = build_dashboard(get_store())
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


class SetAside(BaseModel):
    event_id: str
    weekly: float = Field(gt=0, le=10_000)


@app.post("/setasides")
def create_set_aside(body: SetAside) -> dict[str, Any]:
    from nataware.conversation.tools import set_aside

    try:
        return set_aside(body.event_id, body.weekly)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.delete("/setasides/{event_id}")
def delete_set_aside(event_id: str) -> dict[str, Any]:
    store = get_store()
    rest = [s for s in store.get("set_asides") or [] if s["event_id"] != event_id]
    store.put("set_asides", rest)
    return {"set_asides": rest}


@app.get("/recurring")
def recurring() -> dict[str, Any]:
    from nataware.insights.recurring import committed_monthly, detect_recurring

    items = detect_recurring(get_store().transactions, settings.demo_today)
    return {"recurring": items, "committed": committed_monthly(items)}


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
    limit: int | None = Query(None, ge=1, le=2000),
    newest_first: bool = False,
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
    total = round(sum(t["amount"] for t in txns if t["direction"] == "debit"), 2)
    if newest_first:
        txns = list(reversed(txns))
    shown = txns[:limit] if limit else txns
    return {"count": len(txns), "total_debits": total, "transactions": [q.public_view(t) for t in shown]}


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


@app.post("/chat/stream")
def chat_stream(body: ChatRequest) -> StreamingResponse:
    """Server-sent events version of /chat, for a live, speakable UI.

    Events: `session` {session_id, mode} first, then any number of `sentence` {text} and
    `tool` {tool, input, result}, then `done` {reply, profile?, complete?} or `error` {message}.
    Sentences arrive while Claude is still generating, so the UI can start speaking at once.
    """
    from nataware.conversation.sessions import CoachSession, OnboardingSession

    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured")

    session_id = body.session_id or uuid.uuid4().hex
    session = _sessions.get(session_id)
    if session is None:
        try:
            session = OnboardingSession() if body.mode == "onboarding" else CoachSession()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        _sessions[session_id] = session
    mode = "onboarding" if isinstance(session, OnboardingSession) else "coach"

    events: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()

    def on_sentence(text: str) -> None:
        events.put(("sentence", {"text": text}))

    def on_tool(name: str, args: dict, result: dict) -> None:
        events.put(("tool", {"tool": name, "input": args, "result": result}))

    def run() -> None:
        try:
            if isinstance(session, OnboardingSession):
                reply = session.reply(body.message, on_sentence) if session.message_history else session.start(on_sentence)
                profile = session.profile.model_dump(mode="json") if session.profile else None
                events.put(("done", {"reply": reply, "profile": profile, "complete": profile is not None}))
            else:
                reply = session.reply(body.message, on_sentence, on_tool)
                events.put(("done", {"reply": reply}))
        except Exception as exc:  # surface to the UI rather than hanging the stream
            events.put(("error", {"message": f"{type(exc).__name__}: {exc}"}))
        finally:
            events.put(None)

    threading.Thread(target=run, name=f"chat-{session_id[:8]}", daemon=True).start()

    def stream():
        yield _sse("session", {"session_id": session_id, "mode": mode})
        while (item := events.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


# ---------------------------------------------------------------------- browser voice
_AUDIO_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
              "audio/wav": "wav", "audio/x-wav": "wav", "audio/aac": "m4a"}
MAX_AUDIO_BYTES = 15 * 1024 * 1024


@app.post("/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)) -> dict[str, str]:
    """Speech-to-text (Whisper) for audio recorded in the browser."""
    from nataware.voice.stt import transcribe_bytes

    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY is not configured")
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty recording")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too long")
    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext = _AUDIO_EXT.get(content_type) or Path(audio.filename or "").suffix.lstrip(".") or "webm"
    try:
        text = transcribe_bytes(data, f"speech.{ext}")
    except Exception as exc:
        raise HTTPException(502, f"Transcription failed: {type(exc).__name__}") from exc
    return {"text": text}


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@app.post("/voice/speak")
def voice_speak(body: SpeakRequest) -> StreamingResponse:
    """Text-to-speech (ElevenLabs), streamed back as MP3 so playback can start immediately."""
    import httpx

    from nataware.voice.tts import _TTS_URL

    if not settings.elevenlabs_api_key:
        raise HTTPException(503, "ELEVENLABS_API_KEY is not configured")
    client = httpx.Client(timeout=httpx.Timeout(30.0, read=60.0))
    request = client.build_request(
        "POST",
        _TTS_URL.format(voice_id=settings.elevenlabs_voice_id),
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": settings.elevenlabs_api_key},
        json={"text": body.text, "model_id": settings.elevenlabs_model},
    )
    resp = client.send(request, stream=True)
    if resp.status_code >= 400:
        resp.read()
        detail = resp.text[:200]
        resp.close()
        client.close()
        raise HTTPException(502, f"ElevenLabs {resp.status_code}: {detail}")

    def audio():
        try:
            yield from resp.iter_bytes()
        finally:
            resp.close()
            client.close()

    return StreamingResponse(audio(), media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
