"""NatAware command line.

    python -m nataware                      # voice onboarding, then talk to NatBot
    python -m nataware --skip-onboarding    # straight to the coach with the saved/demo profile
    python -m nataware --text               # type instead of speaking (no microphone / Whisper)
    python -m nataware --no-tts             # print replies only (no ElevenLabs)
    python -m nataware trigger temporal     # fire a coaching trigger: transaction | macro | temporal
    python -m nataware reset                # restore the fake seed data
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from nataware import AGENT_NAME
from nataware.config import settings
from nataware.render import console, render_nudge, render_profile, render_tool_result

EXIT_RE = re.compile(r"^\W*(bye|goodbye|good bye|exit|quit|stop|that's all|thats all)\W*$", re.IGNORECASE)


class VoiceIO:
    """Input from the mic (VAD + Whisper) or keyboard; output to terminal + ElevenLabs."""

    def __init__(self, text_mode: bool, tts: bool) -> None:
        self.text_mode = text_mode
        self.speaker = None
        if tts:
            from nataware.voice.tts import Speaker

            self.speaker = Speaker()
        self._line_open = False

    # -- output
    def begin_reply(self) -> None:
        console.print(f"\n[bold cyan]{AGENT_NAME}:[/] ", end="")
        self._line_open = True

    def sentence(self, text: str) -> None:
        if not self._line_open:
            console.print("[cyan]   [/]", end="")
            self._line_open = True
        console.print(f"[cyan]{text}[/]", end=" ", soft_wrap=True)
        if self.speaker:
            self.speaker.say(text)

    def tool(self, name: str, args: dict, result: dict) -> None:
        if self._line_open:
            console.print()
            self._line_open = False
        render_tool_result(name, args, result)

    def end_reply(self) -> None:
        if self._line_open:
            console.print()
            self._line_open = False

    # -- input
    def listen(self) -> str:
        if self.speaker:
            self.speaker.wait()  # don't record NatBot's own voice
        if self.text_mode:
            return console.input("\n[bold]You:[/] ").strip()

        from nataware.voice.capture import record_utterance
        from nataware.voice.stt import transcribe

        while True:
            console.print("\n[dim]🎙  Listening… (just start talking)[/]")
            wav: Path | None = record_utterance()
            if wav is None:
                console.print("[dim]   …still here whenever you're ready.[/]")
                continue
            try:
                with console.status("[dim]Transcribing…[/]"):
                    text = transcribe(wav)
            finally:
                wav.unlink(missing_ok=True)
            if text:
                console.print(f"[bold]You:[/] {text}")
                return text
            console.print("[dim]   (didn't catch that - try again)[/]")

    def close(self) -> None:
        if self.speaker:
            self.speaker.wait()
            self.speaker.close()


def _check_keys(text_mode: bool, tts: bool) -> list[str]:
    missing = []
    if not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if not text_mode and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY (or use --text)")
    if tts and not settings.elevenlabs_api_key:
        missing.append("ELEVENLABS_API_KEY (or use --no-tts)")
    return missing


def talk(text_mode: bool, tts: bool, skip_onboarding: bool) -> int:
    from nataware.conversation.sessions import CoachSession, OnboardingSession
    from nataware.data.store import get_store
    from nataware.worker.tasks import bootstrap

    missing = _check_keys(text_mode, tts)
    if missing:
        console.print("[red]Missing configuration:[/] " + ", ".join(missing) + "\nCopy .env.example to .env and fill it in.")
        return 2

    bootstrap()
    io = VoiceIO(text_mode=text_mode, tts=tts)
    try:
        console.rule(f"[bold]NatAware[/] · {AGENT_NAME}")
        if not skip_onboarding:
            onboarding = OnboardingSession()
            io.begin_reply()
            onboarding.start(io.sentence)
            io.end_reply()
            while onboarding.profile is None:
                user = io.listen()
                if not user:
                    continue
                if EXIT_RE.match(user):
                    return 0
                io.begin_reply()
                onboarding.reply(user, io.sentence)
                io.end_reply()
            if io.speaker:
                io.speaker.wait()
            render_profile(onboarding.profile)
        else:
            render_profile(get_store().get_profile())

        coach = CoachSession()
        console.print(
            "[dim]Ask me anything about your spending - e.g. \"highlight where I spent on alcohol\", "
            "\"how did I do last month?\", \"any threats coming up?\". Say \"goodbye\" to finish.[/]"
        )
        while True:
            user = io.listen()
            if not user:
                continue
            if EXIT_RE.match(user):
                io.begin_reply()
                io.sentence("Nice one. Catch you soon.")
                io.end_reply()
                return 0
            io.begin_reply()
            coach.reply(user, io.sentence, io.tool)
            io.end_reply()
    except KeyboardInterrupt:
        console.print("\n[dim]Bye.[/]")
        return 0
    finally:
        io.close()


def trigger(kind: str) -> int:
    from nataware.worker.tasks import bootstrap, generate_intervention

    bootstrap()
    render_nudge(generate_intervention.delay(kind).get())
    return 0


def reset() -> int:
    from nataware.data.store import get_store
    from nataware.worker.tasks import bootstrap

    get_store().reset()
    bootstrap()
    console.print("[green]Demo data reset to the seed state.[/]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nataware", description=f"Talk to {AGENT_NAME}.")
    parser.add_argument("--text", action="store_true", help="type instead of speaking")
    parser.add_argument("--no-tts", action="store_true", help="don't speak replies aloud")
    parser.add_argument("--skip-onboarding", action="store_true", help="use the saved profile")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")
    t = sub.add_parser("trigger", help="fire a coaching trigger")
    t.add_argument("kind", choices=["transaction", "macro", "temporal"])
    sub.add_parser("reset", help="restore the fake seed data")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if sys.platform == "win32":
        # Let rich print £, emoji and box-drawing characters on older Windows consoles.
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    if args.command == "trigger":
        return trigger(args.kind)
    if args.command == "reset":
        return reset()
    return talk(text_mode=args.text, tts=not args.no_tts, skip_onboarding=args.skip_onboarding)
