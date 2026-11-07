"""Money Coach - a concept feature shown inside a NatWest-style online banking screen.

Run:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from money_coach import engine, voice  # noqa: E402  (needs env loaded first)

st.set_page_config(page_title="Money Coach | Online Banking", page_icon="💜", layout="wide")

PURPLE, DEEP, LILAC = "#5a287d", "#3c1053", "#f1e9f6"
GREEN, AMBER, RED, GREY = "#1e7d4f", "#c46a00", "#c8102e", "#8a8590"
SEVERITY_COLORS = {"low": GREEN, "medium": AMBER, "high": RED}
DISCRETIONARY = {"Food Delivery", "Eating Out", "Shopping", "Entertainment",
                 "Self-care", "Taxis", "Subscriptions"}
FONT = "Inter, Helvetica Neue, Arial, sans-serif"

# --------------------------------------------------------------------------
# Styling - bank chrome on top of Streamlit
# --------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"], .stMarkdown, button, input {{ font-family: {FONT}; }}
    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer,
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display: none !important; }}
    .stApp {{ background: #f5f4f7; overflow-x: hidden; }}
    .block-container {{ max-width: 1160px; padding-top: 0 !important; padding-bottom: 3rem; }}

    /* full-bleed bank header */
    .nw-bleed {{ width: 100vw; margin-left: calc(50% - 50vw); }}
    .nw-top {{ background: {DEEP}; color: #fff; margin-top: -1rem; }}
    .nw-inner {{ max-width: 1160px; margin: 0 auto; padding: 0 1rem; display: flex;
                align-items: center; justify-content: space-between; }}
    .nw-top .nw-inner {{ height: 64px; }}
    .nw-brand {{ font-weight: 800; font-size: 1.55rem; letter-spacing: -.02em; color: #fff; }}
    .nw-brand small {{ font-weight: 400; font-size: .85rem; opacity: .75; margin-left: .7rem;
                      letter-spacing: 0; border-left: 1px solid rgba(255,255,255,.35); padding-left: .7rem; }}
    .nw-top-links {{ font-size: .88rem; display: flex; gap: 1.4rem; align-items: center; }}
    .nw-top-links span {{ opacity: .9; }}
    .nw-logout {{ border: 1px solid rgba(255,255,255,.7); border-radius: 999px; padding: .3rem .95rem; }}
    .nw-nav {{ background: {PURPLE}; }}
    .nw-nav .nw-inner {{ height: 50px; justify-content: flex-start; gap: 2rem; }}
    .nw-nav span {{ color: #fff; font-size: .93rem; font-weight: 500; opacity: .85; padding: 14px 0; }}
    .nw-nav span.active {{ opacity: 1; font-weight: 700; border-bottom: 3px solid #fff; }}
    .nw-nav span.nw-new {{ background: #fff; color: {PURPLE}; font-size: .62rem; font-weight: 800; border-radius: 4px;
              padding: 1px 5px; margin-left: 6px; vertical-align: middle; letter-spacing: .04em; opacity: 1; border: 0; }}
    .nw-crumb {{ font-size: .82rem; color: #6b6570; margin: 1.3rem 0 .2rem; }}
    .nw-crumb b {{ color: {PURPLE}; font-weight: 600; }}
    h1.nw-h1 {{ font-size: 2rem; font-weight: 800; color: {DEEP}; margin: 0 0 .2rem; padding: 0; }}
    .nw-sub {{ color: #5c5661; margin-bottom: 1rem; }}

    /* cards */
    .nw-card {{ background: #fff; border-radius: 12px; padding: 1.2rem 1.35rem;
               box-shadow: 0 1px 3px rgba(60,16,83,.08), 0 1px 1px rgba(60,16,83,.04);
               border: 1px solid #ebe7ef; height: 100%; }}
    .nw-label {{ font-size: .76rem; color: #6b6570; text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }}
    .nw-acct {{ font-weight: 700; color: {DEEP}; font-size: 1.05rem; margin: .25rem 0 0; }}
    .nw-acct-sub {{ color: #6b6570; font-size: .85rem; }}
    .nw-bal {{ font-size: 2rem; font-weight: 800; color: #2b2730; margin-top: .35rem; }}
    .nw-bal small {{ font-size: .85rem; font-weight: 500; color: #6b6570; margin-left: .3rem; }}
    .nw-arch {{ font-size: 1.35rem; font-weight: 800; color: {PURPLE}; margin: .25rem 0; }}
    .nw-chip {{ display: inline-block; background: {LILAC}; color: {DEEP}; border-radius: 999px;
               padding: .18rem .7rem; font-size: .78rem; font-weight: 600; margin: .2rem .3rem 0 0; }}
    .nw-pill {{ display: inline-block; color: #fff; border-radius: 4px; padding: .1rem .5rem;
               font-size: .7rem; font-weight: 700; letter-spacing: .04em; margin-right: .35rem; }}

    /* threat cards */
    .nw-threat {{ border-left: 5px solid; }}
    .nw-threat h4 {{ color: {DEEP}; font-size: 1.05rem; font-weight: 700; margin: .55rem 0 .6rem; padding: 0; }}
    .nw-row {{ font-size: .87rem; color: #3d3842; margin: .35rem 0; line-height: 1.45; }}
    .nw-row b {{ color: {DEEP}; }}
    .nw-cost {{ font-size: 1.55rem; font-weight: 800; color: #2b2730; margin-top: .7rem; }}
    .nw-cost span {{ font-size: .8rem; font-weight: 500; color: #6b6570; }}
    .nw-tip {{ background: {LILAC}; border-radius: 8px; padding: .65rem .8rem; font-size: .85rem;
              color: {DEEP}; margin-top: .7rem; }}
    .nw-tip b {{ display: block; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; margin-bottom: .15rem; }}
    .nw-banner {{ background: linear-gradient(100deg, {DEEP}, {PURPLE}); color: #fff; border-radius: 12px;
                 padding: 1.2rem 1.5rem; margin: .4rem 0 1rem; }}
    .nw-banner .nw-label {{ color: rgba(255,255,255,.75); }}
    .nw-banner div.big {{ font-size: 1.25rem; font-weight: 700; margin-top: .2rem; }}

    /* tabs as a sub-navigation */
    .stTabs [role="tablist"] {{ gap: 1.8rem; padding-left: 4px; }}
    .stTabs [role="tab"] {{ height: 46px; font-weight: 600; color: #5c5661; }}
    .stTabs [role="tab"] p {{ font-size: .95rem; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{ color: {PURPLE} !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background: {PURPLE}; height: 3px; }}

    /* buttons, inputs, chat */
    .stButton > button, .stFormSubmitButton > button {{ border-radius: 999px; font-weight: 600; padding: .45rem 1.3rem; }}
    .stButton > button[kind="secondary"], .stFormSubmitButton > button {{ border: 1.5px solid {PURPLE}; color: {PURPLE}; background: #fff; }}
    [data-testid="stChatMessage"] {{ background: #fff; border: 1px solid #ebe7ef; border-radius: 12px; padding: .9rem 1rem; }}
    [data-testid="stTextInput"] input {{ border-radius: 8px; }}
    [data-testid="stMetric"] {{ background: #fff; border: 1px solid #ebe7ef; border-radius: 12px; padding: 1rem 1.2rem; }}
    [data-testid="stMetricLabel"] p {{ color: #6b6570; font-weight: 600; }}
    [data-testid="stMetricValue"] {{ color: #2b2730; font-weight: 800; }}
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{ background: #fff; border: 1px solid #ebe7ef;
        border-radius: 12px; padding: .5rem; }}
    [data-testid="stExpander"] details {{ background: #fff; border-radius: 12px; }}
    .nw-foot {{ color: #8a8590; font-size: .78rem; text-align: center; margin-top: 2.5rem; }}
    @media (max-width: 760px) {{
        .nw-top-links span:not(.nw-logout) {{ display: none; }}
        .nw-nav .nw-inner {{ gap: 1.1rem; overflow-x: auto; }}
        .nw-nav span {{ white-space: nowrap; font-size: .85rem; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style_fig(fig, height=320, title=None):
    fig.update_layout(
        template="plotly_white", height=height, font=dict(family=FONT, color="#3d3842", size=12),
        title=dict(text=title, font=dict(size=15, color=DEEP)) if title else None,
        margin=dict(l=10, r=10, t=50 if title else 10, b=10),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", legend_title=None,
    )
    return fig


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
defaults = {
    "history": [], "profile": None, "threats": None, "audio_reply": None,
    "autoplay": False, "last_audio_hash": None, "mic_round": 0,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

city_data = engine.load_json("city_news.json")
claude_ok = engine.has_claude_key()
eleven_ok = bool(os.getenv("ELEVENLABS_API_KEY"))

# --------------------------------------------------------------------------
# Bank chrome
# --------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="nw-bleed nw-top"><div class="nw-inner">
      <div class="nw-brand">NatWest<small>Online Banking</small></div>
      <div class="nw-top-links"><span>Hi, Alex</span><span>Messages</span><span>Help</span>
        <span class="nw-logout">Log out</span></div>
    </div></div>
    <div class="nw-bleed nw-nav"><div class="nw-inner">
      <span>My accounts</span><span>Payments &amp; transfers</span><span>Cards</span>
      <span>Insights</span><span class="active">Money Coach<span class="nw-new">NEW</span></span>
    </div></div>
    """,
    unsafe_allow_html=True,
)

head_l, head_r = st.columns([5, 1.3], vertical_alignment="bottom")
with head_l:
    st.markdown(
        '<div class="nw-crumb">My accounts › <b>Money Coach</b></div>'
        '<h1 class="nw-h1">Money Coach</h1>'
        '<div class="nw-sub">A two-minute chat that helps us spot your money pressure points '
        'before they happen.</div>',
        unsafe_allow_html=True)
with head_r:
    with st.popover("Prototype settings", use_container_width=True):
        st.caption(("✅" if claude_ok else "⚠️") + " Claude API key   " + ("✅" if eleven_ok else "⚠️") + " ElevenLabs key")
        demo = st.toggle("Offline demo mode", value=not claude_ok,
                         help="Scripted answers, no API calls. Your safety net on stage.")
        use_voice = st.toggle("Speak replies", value=eleven_ok, disabled=not eleven_ok)
        web_search = st.toggle("Live web search for local news", value=False, disabled=demo)
        st.caption(f"Location (mocked): **{city_data['city']}** · Model: `{engine.MODEL}`")
        if st.button("Reset demo", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------
def say(text: str):
    st.session_state.audio_reply = voice.speak(text) if use_voice else None
    st.session_state.autoplay = True


def build_threats():
    with st.spinner(f"Checking what's coming up in {city_data['city']}…"):
        try:
            st.session_state.threats = engine.generate_threats(
                st.session_state.profile, city_data, demo=demo, use_web_search=web_search)
        except Exception as e:  # keep the demo alive
            st.warning(f"Live forecast unavailable ({e}). Showing the cached forecast.")
            st.session_state.threats = engine.demo_threats()


def run_turn():
    with st.spinner("Wren is thinking…"):
        try:
            reply, profile = engine.interview_turn(st.session_state.history, demo=demo)
        except Exception as e:
            st.error(f"Couldn't reach the coach: {e}. Turn on offline demo mode in Prototype settings.")
            return
    st.session_state.history.append({"role": "assistant", "content": reply})
    say(reply)
    if profile:
        st.session_state.profile = profile
        build_threats()


def submit_answer(text: str):
    text = text.strip()
    if not text:
        return
    st.session_state.history.append({"role": "user", "content": text})
    run_turn()
    st.session_state.mic_round += 1
    st.rerun()


# --------------------------------------------------------------------------
# Account strip
# --------------------------------------------------------------------------
profile = st.session_state.profile
threats = st.session_state.threats
a1, a2, a3 = st.columns([1.15, 1, 1])
with a1:
    st.markdown(
        """<div class="nw-card"><div class="nw-label">Current account</div>
        <div class="nw-acct">Select Account</div>
        <div class="nw-acct-sub">60-XX-XX &nbsp;·&nbsp; ••••4821</div>
        <div class="nw-bal">£1,842.37<small>balance</small></div>
        <div class="nw-acct-sub">£2,342.37 available, including £500 arranged overdraft</div></div>""",
        unsafe_allow_html=True)
with a2:
    if profile:
        chips = "".join(f'<span class="nw-chip">{t}</span>' for t in profile.get("emotional_triggers", [])[:3])
        st.markdown(f"""<div class="nw-card"><div class="nw-label">Your money personality</div>
            <div class="nw-arch">{profile['archetype']}</div>
            <div class="nw-acct-sub">{profile.get('archetype_blurb', '')}</div>{chips}</div>""",
                    unsafe_allow_html=True)
    else:
        st.markdown("""<div class="nw-card"><div class="nw-label">Your money personality</div>
            <div class="nw-arch">Not set up yet</div>
            <div class="nw-acct-sub">Chat to Wren for about two minutes, by voice or text, to unlock your
            personalised forecast.</div></div>""", unsafe_allow_html=True)
with a3:
    if threats:
        total = sum(t["estimated_cost_gbp"] for t in threats["threats"])
        lvl = threats.get("overall_threat_level", 0)
        word, colr = ("High", RED) if lvl >= 66 else ("Medium", AMBER) if lvl >= 33 else ("Low", GREEN)
        st.markdown(f"""<div class="nw-card"><div class="nw-label">Next 30 days</div>
            <div class="nw-bal">£{total:,}<small>predicted pressure</small></div>
            <span class="nw-pill" style="background:{colr}">{word.upper()} RISK</span>
            <span class="nw-acct-sub">{len(threats['threats'])} pressure points found in {threats.get('city', '')}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="nw-card"><div class="nw-label">Next 30 days</div>
            <div class="nw-bal" style="color:#b9b3bf">£ —</div>
            <div class="nw-acct-sub">We'll compare your habits with what's coming up in
            {city_data['city']}: weather, health, transport and prices.</div></div>""",
                    unsafe_allow_html=True)

st.write("")
tab_chat, tab_month, tab_spend = st.tabs(["Talk to your coach", "Your month ahead", "Spending insights"])

# --------------------------------------------------------------------------
# Tab 1 - voice onboarding
# --------------------------------------------------------------------------
with tab_chat:
    history = st.session_state.history
    answered = sum(1 for m in history if m["role"] == "user" and not m.get("opener"))
    chat_col, side_col = st.columns([2.2, 1], gap="large")

    with side_col:
        st.markdown(
            """<div class="nw-card"><div class="nw-label">How it works</div>
            <div class="nw-row">1. Answer four quick questions about everyday moments. We won't ask about your bank balance.</div>
            <div class="nw-row">2. Wren works out your money personality and the moments you're most likely to overspend.</div>
            <div class="nw-row">3. We match that against what's happening locally next month and warn you early.</div>
            <div class="nw-row" style="margin-top:.8rem;color:#6b6570;font-size:.78rem">🔒 Your answers are only used
            to personalise Money Coach. You can delete them at any time.</div></div>""",
            unsafe_allow_html=True)

    with chat_col:
        if not history:
            st.markdown(
                """<div class="nw-card" style="padding:1.6rem 1.6rem 1.2rem">
                <div class="nw-arch" style="color:#3c1053">Hi Alex, I'm Wren 👋</div>
                <div class="nw-row" style="font-size:.95rem">I'm your Money Coach. Instead of asking about spreadsheets, I'll
                ask you about a few everyday moments. From your answers, I can spot when your spending is most likely
                to slip, before it happens.</div></div>""",
                unsafe_allow_html=True)
            st.write("")
            if st.button("Start chat", type="primary"):
                history.append({"role": "user", "content": "Hi, I'm ready to start.", "opener": True})
                run_turn()
                st.rerun()
        else:
            done = bool(st.session_state.profile)
            st.progress(1.0 if done else min(answered, 4) / 4,
                        text="All done" if done else f"Question {min(answered + 1, 4)} of 4")
            for m in history:
                if m.get("opener"):
                    continue
                is_coach = m["role"] == "assistant"
                with st.chat_message("assistant" if is_coach else "user",
                                     avatar=":material/graphic_eq:" if is_coach else ":material/person:"):
                    st.write(m["content"])

            if st.session_state.audio_reply:
                st.audio(st.session_state.audio_reply, format="audio/mpeg",
                         autoplay=st.session_state.autoplay)
                st.session_state.autoplay = False

            if done:
                st.success("Your forecast is ready. Open **Your month ahead** to see it.")
            else:
                audio = st.audio_input("Tap the mic and answer out loud",
                                       key=f"mic_{st.session_state.mic_round}")
                if audio is not None:
                    raw = audio.getvalue()
                    digest = hashlib.sha1(raw).hexdigest()
                    if digest != st.session_state.last_audio_hash:
                        st.session_state.last_audio_hash = digest
                        with st.spinner("Listening…"):
                            try:
                                text = voice.transcribe(raw)
                            except Exception as e:
                                st.error(str(e))
                                text = ""
                        if text:
                            submit_answer(text)

                with st.form("typed", clear_on_submit=True, border=False):
                    c_in, c_btn = st.columns([5, 1], vertical_alignment="bottom")
                    typed = c_in.text_input("Or type your answer", placeholder="Type your answer…")
                    if c_btn.form_submit_button("Send", use_container_width=True):
                        submit_answer(typed)

# --------------------------------------------------------------------------
# Tab 2 - month ahead (the threat dashboard)
# --------------------------------------------------------------------------
with tab_month:
    if not profile:
        st.markdown('<div class="nw-card"><div class="nw-arch" style="color:#3c1053">Your forecast is locked</div>'
                    '<div class="nw-row">Have a quick chat with Wren first. Or, for the demo, load a sample customer.</div></div>',
                    unsafe_allow_html=True)
        st.write("")
        if st.button("Load sample customer"):
            st.session_state.profile = engine.demo_profile()
            build_threats()
            st.rerun()
    else:
        if not threats:
            build_threats()
            threats = st.session_state.threats

        st.markdown(f"""<div class="nw-banner"><div class="nw-label">Your month ahead · {threats.get('city', '')}</div>
            <div class="big">{threats.get('month_outlook', '')}</div></div>""", unsafe_allow_html=True)

        cols = st.columns(len(threats["threats"]))
        for i, (col, t) in enumerate(zip(cols, threats["threats"]), start=1):
            sev = t.get("severity", "medium")
            c = SEVERITY_COLORS.get(sev, GREY)
            with col:
                st.markdown(
                    f"""<div class="nw-card nw-threat" style="border-left-color:{c}">
                    <span class="nw-pill" style="background:{DEEP}">#{i}</span>
                    <span class="nw-pill" style="background:{c}">{sev.upper()}</span>
                    <span class="nw-pill" style="background:{PURPLE}">{t.get('window', '')}</span>
                    <h4>{t['title']}</h4>
                    <div class="nw-row"><b>What's happening:</b> {t['local_signal']}</div>
                    <div class="nw-row"><b>Why it affects you:</b> {t['psych_trigger']}</div>
                    <div class="nw-row">{t['prediction']}</div>
                    <div class="nw-cost">£{t['estimated_cost_gbp']:,}
                      <span>· {t['probability']}% likely · {t.get('category', '')}</span></div>
                    <div class="nw-tip"><b>Coach tip</b>{t['countermeasure']}</div>
                    </div>""",
                    unsafe_allow_html=True)

        st.write("")
        m_l, m_r = st.columns([1.6, 1], gap="medium")
        with m_l:
            tdf = pd.DataFrame(threats["threats"])
            tdf["n"] = [f"#{i}" for i in range(1, len(tdf) + 1)]
            ymax = tdf["estimated_cost_gbp"].max() * 1.45
            matrix = px.scatter(
                tdf, x="probability", y="estimated_cost_gbp", size="estimated_cost_gbp", color="severity",
                color_discrete_map=SEVERITY_COLORS, text="n", size_max=48,
                hover_name="title", hover_data={"window": True, "category": True, "n": False},
                labels={"probability": "How likely (%)", "estimated_cost_gbp": "Predicted cost (£)"})
            matrix.update_traces(textposition="middle center", textfont=dict(size=13, color="#fff"))
            matrix.update_layout(legend=dict(orientation="h", y=1.02, x=0, yanchor="bottom"))
            matrix.add_shape(type="rect", x0=50, x1=105, y0=ymax * .45, y1=ymax,
                             fillcolor="rgba(200,16,46,.06)", line_width=0, layer="below")
            matrix.add_annotation(x=103, y=ymax * .97, text="Act now", showarrow=False,
                                  font=dict(color=RED, size=12), xanchor="right")
            matrix.update_layout(xaxis_range=[0, 105], yaxis_range=[0, ymax], yaxis_tickprefix="£")
            st.plotly_chart(style_fig(matrix, 380, "Pressure map: how likely vs. how costly"),
                            use_container_width=True)
        with m_r:
            traits = pd.DataFrame({
                "trait": ["Stress spending", "Lifestyle creep", "Impulse control", "Risk appetite"],
                "score": [profile.get("stress_spending_risk", 0), profile.get("lifestyle_inflation", 0),
                          profile.get("impulse_control", 0), profile.get("risk_tolerance", 0)],
            })
            fig = px.bar(traits, x="score", y="trait", orientation="h", range_x=[0, 112], text="score")
            fig.update_xaxes(tickvals=[0, 25, 50, 75, 100])
            fig.update_traces(marker_color=PURPLE, textposition="outside")
            fig.update_layout(yaxis_title=None, xaxis_title=None, yaxis=dict(autorange="reversed"))
            st.plotly_chart(style_fig(fig, 380, "Your money personality"), use_container_width=True)

        osp = profile.get("optimum_spending_profile", {})
        cap = osp.get("daily_discretionary_cap_gbp", 0)
        p_l, p_r = st.columns([1, 1.6], gap="medium")
        with p_l:
            donut = go.Figure(go.Pie(
                labels=["Needs", "Wants", "Savings"],
                values=[osp.get("needs_pct", 50), osp.get("wants_pct", 30), osp.get("savings_pct", 20)],
                hole=.62, marker_colors=[DEEP, "#a77bc4", GREEN], sort=False))
            donut.update_layout(legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"), annotations=[dict(text=f"<b>£{cap}</b><br>a day for fun", showarrow=False,
                                                  font=dict(size=14, color=DEEP))])
            st.plotly_chart(style_fig(donut, 300, "Your ideal monthly split"), use_container_width=True)
        with p_r:
            rules = "".join(f'<div class="nw-row">✓&nbsp; {g}</div>' for g in osp.get("guardrails", []))
            ev = "".join(f'<div class="nw-row" style="color:#6b6570">“{e}”</div>' for e in profile.get("evidence", []))
            st.markdown(f"""<div class="nw-card"><div class="nw-label">Your personal guardrails</div>
                {rules}<div class="nw-label" style="margin-top:1rem">Based on what you told us</div>{ev}</div>""",
                        unsafe_allow_html=True)

        st.write("")
        b1, _ = st.columns([1, 4])
        if b1.button("Refresh forecast"):
            st.session_state.threats = None
            st.rerun()
        with st.expander(f"Local signals we checked for {city_data['city']} ({city_data['note']})"):
            st.dataframe(pd.DataFrame(city_data["headlines"])[["date", "category", "headline", "source"]],
                         hide_index=True, use_container_width=True)

# --------------------------------------------------------------------------
# Tab 3 - spending insights (simulated feed)
# --------------------------------------------------------------------------
with tab_spend:
    tx = pd.DataFrame(engine.load_json("transactions.json"))
    tx["date"] = pd.to_datetime(tx["date"])
    tx["late_night"] = tx["time"].str.slice(0, 2).astype(int) >= 21

    p = profile or engine.demo_profile()
    vulnerable = set(p.get("vulnerable_categories", []))
    tx["trigger_match"] = tx["category"].isin(vulnerable) & tx["late_night"]
    spend = tx[tx["category"] != "Savings"]
    disc = spend[spend["category"].isin(DISCRETIONARY)]
    cap = p.get("optimum_spending_profile", {}).get("daily_discretionary_cap_gbp", 24)
    days = (tx["date"].max() - tx["date"].min()).days + 1
    predicted = sum(t["estimated_cost_gbp"] for t in (threats or engine.demo_threats())["threats"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Spent in the last 30 days", f"£{spend['amount'].sum():,.0f}")
    gap = disc["amount"].sum() / days - cap
    m2.metric("Average fun spend per day", f"£{disc['amount'].sum() / days:,.2f}",
              delta=f"{'-' if gap < 0 else '+'}£{abs(gap):.2f} vs your £{cap} cap", delta_color="inverse")
    m3.metric("Late-night trigger spending", f"£{tx.loc[tx['trigger_match'], 'amount'].sum():,.0f}",
              help="After 9pm, in the categories Wren flagged for you")
    m4.metric("Predicted pressure, next 30 days", f"£{predicted:,}")

    g1, g2 = st.columns(2)
    with g1:
        by_cat = disc.groupby("category", as_index=False)["amount"].sum().sort_values("amount")
        by_cat["group"] = by_cat["category"].isin(vulnerable).map({True: "Your trigger categories", False: "Other"})
        f = px.bar(by_cat, x="amount", y="category", orientation="h", color="group",
                   color_discrete_map={"Your trigger categories": PURPLE, "Other": "#cfc7d6"})
        f.update_layout(yaxis_title=None, xaxis_title=None, xaxis_tickprefix="£",
                        legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(style_fig(f, 340, "Where your fun money went"), use_container_width=True)
    with g2:
        daily = disc.groupby("date", as_index=False)["amount"].sum()
        daily["over"] = daily["amount"] > cap
        f2 = px.bar(daily, x="date", y="amount", color="over",
                    color_discrete_map={True: RED, False: "#a77bc4"})
        f2.add_hline(y=cap, line_dash="dash", line_color=DEEP, annotation_text=f"£{cap} daily cap",
                     annotation_position="top left", annotation_font_color=DEEP)
        f2.update_layout(xaxis_title=None, yaxis_title=None, yaxis_tickprefix="£", showlegend=False)
        st.plotly_chart(style_fig(f2, 340, "Daily fun spend vs. your cap"), use_container_width=True)

    st.markdown('<div class="nw-label" style="margin:.6rem 0 .4rem">Recent transactions · Select Account ••••4821</div>',
                unsafe_allow_html=True)
    show = tx.sort_values(["date", "time"], ascending=False).copy()
    show["Coach flag"] = show.apply(
        lambda r: "⚑ Trigger moment" if r["trigger_match"] else ("☾ Late night" if r["late_night"] else ""), axis=1)
    show["Date"] = show["date"].dt.strftime("%d %b")
    show = show.rename(columns={"time": "Time", "merchant": "Description", "category": "Category", "amount": "Amount"})
    show["Amount"] = -show["Amount"]
    st.dataframe(show[["Date", "Time", "Description", "Category", "Amount", "Coach flag"]],
                 hide_index=True, use_container_width=True, height=420,
                 column_config={"Amount": st.column_config.NumberColumn(format="£%.2f")})

st.markdown('<div class="nw-foot">Concept prototype for demonstration only. Not affiliated with or endorsed by '
            'NatWest Group. All account data, transactions and news are simulated.</div>',
            unsafe_allow_html=True)
