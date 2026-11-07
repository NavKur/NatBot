# NatAware

A voice-first behavioural finance coach. **NatBot** interviews you out loud, builds a
psychological money profile, and then talks you through your spending: highlighting where
your money goes, linking it to your habits, warning you about local threats and nudging you
towards a healthier baseline.

> **This is a demo prototype.** The voice-to-chat loop is real. Everything downstream of it
> (statement ingestion, behavioural tagging, threat engine, coaching triggers) is faked
> with deterministic logic and **synthetic data**, built to the shape of the production
> architecture so each fake can be swapped for the real thing in place.

---

## What's real and what's faked

| Area | Status | Notes |
|---|---|---|
| Mic capture + VAD (`sounddevice`, `webrtcvad`) | ✅ Real | Stops after 1.5 s of silence, buffers to a temp `.wav` |
| Speech-to-text (OpenAI Whisper) | ✅ Real | `audio.transcriptions.create` |
| Onboarding state machine (Claude) | ✅ Real | 3 questions → hidden `<profile>` JSON → validated 2D matrix |
| Text-to-speech (ElevenLabs `eleven_turbo_v2_5`) | ✅ Real | Sentence-chunked, streamed PCM played as it arrives; `<profile>` never spoken |
| Conversational coach (Claude + tools) | ✅ Real | NatBot calls real tools over the fake data: "highlight where I spent on alcohol" |
| Transactions / statements | 🟡 Fake data | 271 synthetic Manchester transactions, Aug–Nov 2026 |
| Statement parsing (pandas / PyMuPDF) | 🟡 Basic | CSV works on simple exports; PDF is a best-effort line parser |
| Behavioural tagging | 🟡 Faked | Rule-based, same output contract as the Claude batch tagger |
| Threat engine (weather / news) | 🟡 Faked | Synthetic `Daily_Macro_Summary`; deterministic scoring |
| Coaching triggers + nudges | 🟡 Faked | Real trigger logic + transition matrix; template nudges; demo delivery |
| PostgreSQL / Redis | 🟡 Stubbed | JSON-backed store + in-process Celery (`DEMO_MODE=true`). Schema and compose file included |

---

## Quick start (Windows / macOS / Linux)

**Use Python 3.11 or 3.12.** Voice packages such as `webrtcvad-wheels` may not have
prebuilt wheels for newer Python versions yet.

```bash
python -m venv .venv
```

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

```bash
pip install -r requirements-dev.txt
```

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

Fill in `.env` with `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and `ELEVENLABS_API_KEY`.

### Talk to NatBot

```bash
python -m nataware
```

1. NatBot introduces itself and asks three questions (windfall, loss aversion, social pressure).
   Just talk; it stops listening when you pause for 1.5 seconds.
2. It speaks a summary and shows your profile (Capacity × Tendency + optimal baseline).
   The fake transactions are re-tagged against your new Tendency.
3. Then ask it anything about your money. Say **"goodbye"** to finish.

Useful flags:

| Command | What it does |
|---|---|
| `python -m nataware --skip-onboarding` | Go straight to the coach using the saved (or demo) profile |
| `python -m nataware --text` | Type instead of speaking (no mic / Whisper needed) |
| `python -m nataware --no-tts` | Print replies only (no ElevenLabs) |
| `python -m nataware --text --no-tts` | Pure text mode: only `ANTHROPIC_API_KEY` needed |
| `python -m nataware trigger temporal` | Fire a coaching trigger (`transaction`, `macro`, `temporal`) |
| `python -m nataware reset` | Restore the seed data (clears profile changes, highlights, nudges) |

### Things to ask

- "Highlight where I spent on alcohol last month."
- "Did I spend anything on gambling?" *(it'll tell you no, because nothing matches)*
- "How much did I spend on takeaways in October?"
- "Show me my late-night online shopping."
- "Why were these flagged?"
- "How did I do against my budget last month?"
- "Any financial threats coming up?"
- "What's my goal this week? How much have I got left?"
- "I just spent £28 on Deliveroo." *(logs it, re-tags, may fire a transaction nudge)*

When NatBot highlights transactions, they render as a table in the terminal and are also
stored for the API (`GET /highlights`) so the front end can show them.

---

## The demo data

- **Today is pinned to 2026-11-07** (`DEMO_TODAY`), so "last month" and "this week" always
  line up with the data no matter when you run it.
- **Demo user:** based in Manchester, salary £2,850/month, spending roughly everything they
  earn. Default profile: *The Scrapper × The Comfort-Buyer* (55/25/20 baseline), assessed
  2026-10-17, so they're on stage 2 of their coaching plan. Completing onboarding replaces it.
- Regenerate the transactions with `python scripts/generate_seed_data.py` (deterministic).
- Runtime changes are written to `data/runtime/state.json` (git-ignored). Delete it, or run
  `python -m nataware reset`, to start fresh.
- All merchants, amounts, weather alerts and news items are **synthetic**. Amounts are in GBP.
  The threat field keeps the blueprint's name, `estimated_dollar_burden`, with `currency: "GBP"`.

---

## API (for the front end)

```bash
uvicorn nataware.api.main:app --reload
```

Docs: <http://127.0.0.1:8000/docs>

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Status, demo mode, pinned date |
| GET | `/profile` | Current Capacity × Tendency profile |
| GET | `/transactions` | Filter by `query`, `category`, `date_from`, `date_to`, `flagged_only`, `direction` |
| POST | `/transactions` | Webhook-style single transaction → tag → transaction trigger |
| POST | `/statements/upload` | Upload a CSV (or PDF) statement → parse → tag |
| POST | `/tagging/run` | Run the tagging pipeline (`?retag_all=true` to redo all) |
| GET | `/highlights` | Transaction sets NatBot highlighted in conversation |
| GET | `/spending/summary` | Totals by `category` / `merchant` / `month` / `bucket` |
| GET | `/budget` | Needs/Wants/Savings vs optimal baseline for a `month` |
| GET | `/threats` · POST `/threats/refresh` | Daily macro summary + active threats |
| GET | `/coaching/plan` | Current stage, micro-goals, weekly limit and progress |
| GET | `/nudges` · POST `/triggers/{kind}` | Delivered nudges; fire `transaction` / `macro` / `temporal` |
| POST | `/chat` | **Real** text chat with NatBot (`mode: onboarding \| coach`). Returns `tool_events` so the UI can render highlights |
| POST | `/demo/reset` | Reset to seed data |

The voice pipeline currently runs in the local CLI, as the blueprint specifies (client-side
capture). `/chat` gives the front end the same brain over text. Wiring browser audio into
the API is the natural next step when the UI is merged.

---

## Project layout

```
NatAware/
├── nataware/
│   ├── cli.py                  # python -m nataware - voice loop entry point
│   ├── config.py               # settings from .env
│   ├── profile.py              # Capacity × Tendency matrix, <profile> extraction
│   ├── render.py               # terminal rendering of tool results
│   ├── voice/                  # Phase 1 (real)
│   │   ├── capture.py          #   mic + webrtcvad → .wav
│   │   ├── stt.py              #   Whisper
│   │   ├── chunker.py          #   stream → sentences, hides <profile>
│   │   └── tts.py              #   ElevenLabs streaming playback
│   ├── conversation/           # Claude (real)
│   │   ├── llm.py              #   streaming + agentic tool-use loop
│   │   ├── prompts.py          #   onboarding state machine + coach prompts
│   │   ├── sessions.py         #   OnboardingSession / CoachSession
│   │   └── tools.py            #   tools NatBot can call
│   ├── data/                   # JSON-backed stand-in for PostgreSQL
│   ├── ingestion/              # Phase 2: parser + behavioural tagging
│   ├── threats/                # Phase 3: macro aggregation + threat matrix
│   ├── coaching/               # Phase 4: transition matrix, triggers, nudges, delivery
│   ├── worker/                 # Celery app, beat schedule, tasks
│   └── api/                    # FastAPI
├── config/transition_matrix.json
├── data/seed/                  # synthetic demo data
├── db/schema.sql               # production PostgreSQL schema
├── scripts/generate_seed_data.py
├── tests/
└── docker-compose.yml          # optional Postgres + Redis
```

---

## Swapping fakes for the real thing

Each faked component keeps the production interface, and most include the prompt the real
version would send:

| Fake | Replace with | Where |
|---|---|---|
| `tag_batch()` rules | Claude call using `build_tagging_prompt()` | `nataware/ingestion/tagging.py` |
| Seeded macro summary | OpenWeatherMap alerts + NewsAPI | `nataware/threats/macro.py` |
| `calculate_threats()` scoring | Claude call using `build_threat_prompt()` | `nataware/threats/engine.py` |
| Template `generate_nudge()` | Claude call using `build_intervention_prompt()` | `nataware/coaching/engine.py` |
| Demo `deliver()` | Push / email / queued ElevenLabs audio | `nataware/coaching/notifications.py` |
| JSON `Store` | SQLAlchemy repository on `db/schema.sql` | `nataware/data/store.py` |
| Eager Celery | `DEMO_MODE=false` + Redis + worker + beat | `nataware/worker/celery_app.py` |

Production-style infrastructure:

```bash
docker compose up -d
```

```bash
celery -A nataware.worker.celery_app worker --loglevel=info --pool=solo
```

```bash
celery -A nataware.worker.celery_app beat --loglevel=info
```

---

## Configuration

See `.env.example`. Notable settings:

- `ANTHROPIC_MODEL` defaults to `claude-sonnet-5-5`. The blueprint names Claude 3.5 Sonnet,
  which has been retired, so the model is configurable.
- `ELEVENLABS_VOICE_ID` sets NatBot's voice (any voice from your ElevenLabs library).
- `VAD_SILENCE_SECONDS` / `VAD_AGGRESSIVENESS` tune turn-taking. Raise aggressiveness (max 3)
  in noisy rooms.

## Tests

```bash
pytest
```

The tests cover sentence chunking and `<profile>` hiding, profile extraction, every coach
tool against the seed data, the streaming tool-use loop (with a fake Claude client), and
the API. They need no API keys and no audio hardware.

## Troubleshooting

- **No audio / wrong mic:** `python -c "import sounddevice; print(sounddevice.query_devices())"`
  shows your devices. The default input and output devices are used.
- **NatBot hears itself:** use headphones. The CLI waits for playback to finish before
  listening, but loud speakers can still bleed into the next recording.
- **`webrtcvad` fails to install:** use Python 3.11 or 3.12.
- **ElevenLabs 401 / 422:** check the key and voice ID. The `pcm_22050` output format is
  available on all plans.
