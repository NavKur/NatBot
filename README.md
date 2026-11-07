# Money Coach

Money Coach is a voice-first onboarding and forecasting prototype for personal banking. It doesn't track money like a ledger. It predicts *when* a customer is about to overspend by combining their psychology with what's happening in their city next month.

> Concept prototype. All account data, transactions and news are simulated.

## How it works

1. **Voice onboarding.** The customer talks to "Wren", a money coach powered by Claude and prompted as a behavioural psychologist. Wren asks 4 story-style questions, such as "Tell me about a time you felt really relieved recently." The answers are transcribed by ElevenLabs Scribe (or the free Google recogniser as a fallback). Wren's replies are spoken back with ElevenLabs text-to-speech.
2. **Hidden profile.** On the final turn, Claude returns a `<profile>{â€¦}</profile>` JSON payload alongside its spoken reply. It holds risk tolerance, impulse control, lifestyle inflation, emotional triggers and an *Optimum Spending Profile*. The app strips the payload out before the reply is shown or spoken.
3. **Threat engine.** The profile is cross-referenced with local signals for a mocked city (Manchester): weather, health, transport and prices. These come from `data/city_news.json`, or from optional live web search. Claude predicts the 3 most likely financial burdens in the next 30 days, each with a cost, probability, date window and countermeasure.
4. **Dashboard.** The app shows the forecast cards, a likelihood Ã— cost pressure map, the spending profile, and spending insights over a fake transaction feed.

## Quick start

```bash
git clone https://github.com/NavKur/NatBot.git
cd NatBot
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
streamlit run app.py
```

Add `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` to `.env` for live mode. With no keys, the app starts in **offline demo mode**, which uses scripted questions and a cached profile and forecast. You can also switch demo mode on during a live demo under *Prototype settings*.

## Project layout

```
app.py                     Streamlit UI
money_coach/
  engine.py                Claude prompts, interview turns, threat engine, offline fallbacks
  voice.py                 Speech-to-text and ElevenLabs text-to-speech
data/
  city_news.json           Mock local signals for the city
  transactions.json        Fake bank feed
  demo_profile.json        Cached profile for offline mode
  demo_threats.json        Cached forecast for offline mode
.streamlit/config.toml     Theme
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Enables live Claude calls |
| `ELEVENLABS_API_KEY` | none | Enables voice in/out |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model used for the interview and forecast |
| `ELEVENLABS_VOICE_ID` | Rachel | TTS voice |
| `ELEVENLABS_MODEL` | `eleven_turbo_v2_5` | TTS model |

## Demo tips

- Rehearse once with live keys, then keep offline demo mode ready as a safety net.
- Keep web search off on stage. The pre-fetched city data is faster and predictable.
- **Load sample customer** on the *Your month ahead* tab jumps straight to the forecast.
