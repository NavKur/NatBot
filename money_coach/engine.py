"""Claude-powered brains: the psych interview and the predictive threat engine.

Every function has an offline "demo" path so a live demo never dies on a
missing key, a rate limit, or bad Wi-Fi.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

PSYCH_SYSTEM_PROMPT = """You are Wren, a warm, sharp money coach trained in behavioural psychology. You live inside the customer's UK mobile/online banking app as the "Money Coach" feature, and you are running a short voice onboarding chat. The customer is in the UK; use British English and pounds (£).

YOUR GOAL
Infer the user's financial habits WITHOUT asking about money directly. People lie about budgets; they don't lie about feelings. From their stories you will estimate:
- risk_tolerance: appetite for uncertainty, novelty, bets, "YOLO" decisions
- impulse_control: ability to delay gratification, especially under stress
- lifestyle_inflation: tendency to upgrade spending as comfort or status rises
- emotional_triggers: the specific moods/situations that make them spend (stress, boredom, loneliness, celebration, bad weather, exhaustion, social comparison...)

THE INTERVIEW
Ask exactly FOUR questions in total, ONE per turn. Make them conversational, specific and story-shaped. Good examples:
1. "Tell me about a time recently when you felt really relieved. What happened right before and right after?"
2. "Picture a long, grey, exhausting week. It's Friday at 7pm. What does the perfect evening look like, honestly?"
3. "When a friend gets something new and shiny - a trip, a car, a gadget - what's the first thought that goes through your head?"
4. "If someone handed you a surprise £1,000 tomorrow with no strings attached, walk me through the first 48 hours."
Adapt questions 2-4 to what they've already told you - follow the interesting thread. Briefly reflect something perceptive about their previous answer before asking the next question (one sentence, never preachy).

VOICE RULES (your words are converted to speech)
- Plain spoken English only. No markdown, no bullet points, no emoji, no stage directions.
- Keep every turn under 70 words. Sound human: contractions, warmth, a little wit.
- Never mention JSON, scores, or that you are profiling them numerically.

THE FINAL TURN
When you are told the interview is complete, give a short spoken "reading" (under 90 words): name their money archetype with a memorable title (e.g. "The Rainy-Day Soother"), one insight that will feel uncannily accurate, and tell them their threat dashboard is ready.
Then, AFTER the spoken reading, output the hidden payload wrapped exactly like this - it is stripped before speech:
<profile>
{
  "archetype": "string - memorable title",
  "archetype_blurb": "one sentence",
  "risk_tolerance": 0-100,
  "impulse_control": 0-100,
  "lifestyle_inflation": 0-100,
  "stress_spending_risk": 0-100,
  "emotional_triggers": ["3-5 short phrases, e.g. 'stress after work', 'grey weather', 'social comparison'"],
  "vulnerable_categories": ["2-4 of exactly: Food Delivery, Eating Out, Shopping, Entertainment, Subscriptions, Taxis, Self-care, Groceries"],
  "optimum_spending_profile": {
    "needs_pct": integer,
    "wants_pct": integer,
    "savings_pct": integer,
    "daily_discretionary_cap_gbp": integer,
    "guardrails": ["3 specific, behavioural rules tailored to their triggers"]
  },
  "evidence": ["3 short quotes or paraphrases from their answers that justify the scores"]
}
</profile>
needs_pct + wants_pct + savings_pct must equal 100. Assume a monthly take-home of about £2,600 when setting the daily cap. The JSON must be valid."""

FINAL_TURN_NOTE = (
    "The user has now answered all four questions. The interview is complete. "
    "Deliver the final spoken reading and then the hidden <profile> JSON payload."
)

THREAT_SYSTEM_PROMPT = """You are the predictive engine behind "Money Coach" in a UK banking app. It forecasts money problems before they happen. Use British English and pounds (£).

You receive (1) a user's behavioural spending profile and (2) local news/signals for their city for the coming month. Cross-reference them to predict the THREE most likely financial burdens the user will face in the next 30 days.

Each threat must sit at the intersection of a psychological trigger AND a local signal - that collision is the whole point. Bad: "You might spend money on food." Good: "The atmospheric river forecast (local) + your habit of soothing grey-day exhaustion with delivery (psych) predicts a delivery binge during the week of Nov 16."

Be concrete: real-sounding pound amounts, a date window, and a probability. Countermeasures must be small, specific and behavioural (pre-commitments, friction, swaps), not generic advice like "make a budget".

Return ONLY this JSON wrapped in <threats></threats> tags, nothing else:
<threats>
{
  "city": "string",
  "month_outlook": "one punchy sentence summarising the user's month",
  "overall_threat_level": 0-100,
  "threats": [
    {
      "title": "short, vivid name, e.g. 'The Atmospheric River Delivery Spiral'",
      "local_signal": "the local event/data point, citing the headline",
      "psych_trigger": "the trait/trigger from the profile it collides with",
      "prediction": "1-2 sentences describing what will likely happen",
      "window": "date range, e.g. '14-20 Nov'",
      "probability": 0-100,
      "estimated_cost_gbp": integer,
      "severity": "low" | "medium" | "high",
      "category": "spending category most affected",
      "countermeasure": "one specific action to take this week"
    }
  ]
}
</threats>"""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def load_json(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def has_claude_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _client():
    import anthropic

    return anthropic.Anthropic()


def _text_of(response) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")


def _call_claude(system: str, messages: list, *, effort: str, max_tokens: int, tools=None):
    """One Claude call with server-side refusal fallback enabled."""
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_config={"effort": effort},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if tools:
        kwargs["tools"] = tools
    client = _client()
    response = client.beta.messages.create(**kwargs)

    # Server tools (web search) can pause a long turn - resume a few times.
    turns = 0
    while response.stop_reason == "pause_turn" and turns < 3:
        messages = messages + [{"role": "assistant", "content": response.content}]
        kwargs["messages"] = messages
        response = client.beta.messages.create(**kwargs)
        turns += 1

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request.")
    return response


def _extract_tag(text: str, tag: str):
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    if not m:
        return None
    raw = m.group(1).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw)


def strip_hidden(text: str) -> str:
    """Remove the hidden payload so it is never shown or spoken."""
    return re.sub(r"<profile>.*?(</profile>|$)", "", text, flags=re.S).strip()


# --------------------------------------------------------------------------
# Psych interview
# --------------------------------------------------------------------------

TOTAL_QUESTIONS = 4

DEMO_TURNS = [
    "Hi, I'm Wren, your Money Coach. No spreadsheets today, I promise - just stories. "
    "Tell me about a time recently when you felt really relieved. What happened right before, and right after?",
    "That sounds like relief that came from finally letting go of control - interesting. "
    "Picture a long, grey, exhausting week. It's Friday at seven. What does the perfect evening honestly look like?",
    "So comfort is something you'd rather have delivered than go out and get. Very human. "
    "When a friend shows off something new and shiny - a trip, a gadget - what's the very first thought in your head?",
    "Honest answer, I appreciate that. Last one. Someone hands you a surprise thousand pounds tomorrow, "
    "no strings attached. Walk me through the first forty-eight hours.",
]

DEMO_FINAL = (
    "Okay, here's your reading. You're what I'd call The Rainy-Day Soother. You're careful with the big stuff "
    "and genuinely good at saving, but when you're drained, comfort becomes a purchase - and it's usually small, "
    "fast and delivered to your door. Your weak spot isn't greed, it's exhaustion. Your threat dashboard is ready."
)


def demo_profile() -> dict:
    return load_json("demo_profile.json")


def demo_threats() -> dict:
    return load_json("demo_threats.json")


def interview_turn(history: list[dict], demo: bool) -> tuple[str, dict | None]:
    """Given the chat history (user/assistant dicts), return (spoken_text, profile_or_None).

    `history` must end with a user message (or be empty for the opener).
    """
    user_answers = sum(1 for m in history if m["role"] == "user" and not m.get("opener"))
    is_final = user_answers >= TOTAL_QUESTIONS

    if demo or not has_claude_key():
        if is_final:
            return DEMO_FINAL, demo_profile()
        return DEMO_TURNS[min(user_answers, TOTAL_QUESTIONS - 1)], None

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    if not messages:
        messages = [{"role": "user", "content": "Hi, I'm ready to start."}]
    if is_final:
        # Mid-conversation system message: an operator instruction for this turn only.
        messages.append({"role": "system", "content": FINAL_TURN_NOTE})

    response = _call_claude(
        PSYCH_SYSTEM_PROMPT,
        messages,
        effort="low" if not is_final else "medium",
        max_tokens=4000 if not is_final else 8000,
    )
    full = _text_of(response)
    profile = None
    if is_final:
        try:
            profile = _extract_tag(full, "profile")
        except (json.JSONDecodeError, TypeError):
            profile = None
        if profile is None:
            profile = demo_profile()  # never leave the dashboard empty on stage
    return strip_hidden(full), profile


# --------------------------------------------------------------------------
# Predictive threat engine
# --------------------------------------------------------------------------

def generate_threats(profile: dict, city_data: dict, demo: bool, use_web_search: bool = False) -> dict:
    if demo or not has_claude_key():
        return demo_threats()

    user_msg = (
        f"USER PROFILE:\n{json.dumps(profile, indent=2)}\n\n"
        f"CITY: {city_data['city']}\nTODAY: {city_data['as_of']}\n\n"
        f"LOCAL SIGNALS (pre-fetched):\n{json.dumps(city_data['headlines'], indent=2)}"
    )
    tools = None
    if use_web_search:
        user_msg += (
            f"\n\nYou may also run up to 3 web searches for very recent news in {city_data['city']} "
            "(weather, health, transit, events, prices) to sharpen the forecast."
        )
        tools = [{
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": 3,
        }]

    response = _call_claude(
        THREAT_SYSTEM_PROMPT,
        [{"role": "user", "content": user_msg}],
        effort="medium",
        max_tokens=16000,
        tools=tools,
    )
    try:
        result = _extract_tag(_text_of(response), "threats")
    except (json.JSONDecodeError, TypeError):
        result = None
    return result or demo_threats()
