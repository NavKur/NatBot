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
| Web app (React) | ✅ Real | First-run voice interview → profile reveal → dashboard; NatBot panel with voice + text |
| Browser voice | ✅ Real | Mic + silence detection in the browser → Whisper; ElevenLabs replies streamed per sentence. Falls back to the browser's own speech when keys are missing |
| Dashboard "financial time travel" | ✅ Real maths, 🤖 Claude wording | Forecast, seasonal costs, goal timelines, strategies and insights are computed from the data; Claude rewrites them in plain English (cached; templates without a key) |
| Transactions / statements | 🟡 Fake data | 1,202 synthetic Manchester transactions, Sep 2025 – Nov 2026 (a full winter, so seasonality is learnable) |
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

### Run the web app

Two terminals:

```bash
uvicorn nataware.api.main:app --reload          # API on :8000
```

```bash
cd web && npm install && npm run dev             # UI on http://localhost:5173
```

Open <http://localhost:5173>. The first visit runs NatBot's three-question interview (speak
or type), reveals your Capacity × Tendency profile and the goals NatBot picked up, then opens
the dashboard. Use the **NatBot** button (or any "Ask NatBot" link) to keep talking. No API
keys? Choose **Skip and explore with a demo profile** to see the dashboard. **Accessibility →
Reset demo** starts over.

For a demo on one port: `cd web && npm run build`, then `uvicorn nataware.api.server:app`
and open <http://localhost:8000>.

### Talk to NatBot (terminal)

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
- The history runs Sep 2025 – Nov 2026 so last winter is in the data: a Christmas spike,
  higher heating bills, more pharmacy runs and a quieter January. That's what the forecast
  and the "Awareness for you" cards learn from.
- Demo goals: House deposit £15,000 (£2,100 saved) and Emergency fund £3,000 (£450 saved).
  Goals from onboarding share the £2,550 savings pot in `data/seed/account.json`.
- Regenerate with `python scripts/generate_seed_data.py` (deterministic). It also writes
  `account.json` (name, balance, savings pot, payday).
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
| POST | `/demo/reset` | Reset to seed data (and back to first-run onboarding) |
| GET | `/app/state` | First visit or not, the account, which keys are configured |
| POST | `/onboarding/skip` | Use the demo profile without the interview |
| GET | `/dashboard` | Everything the home screen shows, in one payload (see below) |
| POST | `/chat/stream` | Server-sent events: `session`, `sentence`…, `tool`…, `done` / `error` |
| POST | `/voice/transcribe` | Browser audio (webm / mp4 / ogg) → Whisper text |
| POST | `/voice/speak` | Text → ElevenLabs MP3, streamed |
| POST · DELETE | `/setasides` · `/setasides/{event_id}` | "Save £x/week" for a seasonal cost (feeds the winter buffer) |
| GET | `/recurring` | Detected bills and subscriptions, with price changes |

`GET /dashboard` returns `stats`, `goals` (projections + strategies), `forecast`, `noticed`,
`awareness`, `threats`, `recurring`, `plan`, `budget`, `nudges` and `narration.status`
(`pending` while Claude is writing the wording, then `ready`; `templates` without a key).

Voice works in both places: the terminal CLI captures audio locally (as the blueprint
specifies), and the web app records in the browser and uses `/voice/transcribe` and
`/voice/speak`. Both share the same Claude sessions and tools.

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
│   ├── insights/               # "financial time travel" for the dashboard
│   │   ├── forecast.py         #   monthly forecast: last 3 months × last year's season + price rises
│   │   ├── awareness.py        #   seasonal cards (Christmas, heating…) from last year + local news
│   │   ├── goals.py            #   goal timelines + strategies valued from real spending
│   │   ├── noticed.py          #   unusual spending, subscriptions, cash-flow to payday, bill changes
│   │   ├── recurring.py        #   recurring payment detection
│   │   ├── narrate.py          #   Claude rewrites the facts in plain English (cached)
│   │   └── dashboard.py        #   assembles GET /dashboard
│   ├── coaching/               # Phase 4: transition matrix, triggers, nudges, delivery
│   ├── worker/                 # Celery app, beat schedule, tasks
│   └── api/                    # FastAPI
├── web/                        # React + Vite front end (see "Run the web app")
│   └── src/
│       ├── pages/              #   Onboarding, Home, Spending, Recurring, Statements
│       ├── home/               #   dashboard sections + charts
│       ├── components/         #   shell, NatBot panel, conversation, dialogs
│       └── voice/              #   mic + silence detection, speech queue, conversation hook
├── config/transition_matrix.json
├── config/seasonal_events.json
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
- `ANTHROPIC_EFFORT` (`low` | `medium` | `high`, default `medium`): lower makes spoken replies
  faster.
- `ELEVENLABS_VOICE_ID` sets NatBot's voice (any voice from your ElevenLabs library).
- `VAD_SILENCE_SECONDS` / `VAD_AGGRESSIVENESS` tune turn-taking. Raise aggressiveness (max 3)
  in noisy rooms.

## Accessibility and inclusion

- Voice and text everywhere, both always available. Every spoken reply is also on screen,
  and screen readers hear each complete reply once.
- **Accessibility** settings (saved per device): text size, high contrast, easier-reading
  spacing, reduced motion, Plain English wording, spoken replies on/off, hands-free mode.
- Keyboard: skip link, visible focus, dialogs trap focus and close with Escape, and every
  chart has a text summary and a "Show as a table" view.
- Chart colours were checked for colour-blind separation and contrast. Status is never
  shown by colour alone.
- NatBot uses plain words, explains terms like ISA, and points people who sound in hardship
  to free help (MoneyHelper, StepChange, Citizens Advice).
- The web app passes an axe-core WCAG 2.2 AA scan with no violations (home, NatBot panel,
  high-contrast mode, spending).

## Tests

```bash
pytest
```

The tests cover sentence chunking and `<profile>` hiding, profile extraction (including
inferred goals), every coach tool against the seed data, the forecasting / seasonal / goal
engines, the streaming tool-use loop (with a fake Claude client), the SSE chat stream, and
the API. They need no API keys and no audio hardware.

## Troubleshooting

- **No audio / wrong mic:** `python -c "import sounddevice; print(sounddevice.query_devices())"`
  shows your devices. The default input and output devices are used.
- **NatBot hears itself:** use headphones. The CLI waits for playback to finish before
  listening, but loud speakers can still bleed into the next recording.
- **`webrtcvad` fails to install:** use Python 3.11 or 3.12.
- **ElevenLabs 401 / 422:** check the key and voice ID. The `pcm_22050` output format is
  available on all plans.
