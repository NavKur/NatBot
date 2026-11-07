"""Speech-to-text via the OpenAI Whisper API."""

from __future__ import annotations

from pathlib import Path

from nataware.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (needed for Whisper speech-to-text).")
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def transcribe(wav_path: Path) -> str:
    """Transcribe a .wav file to text."""
    with open(wav_path, "rb") as audio:
        result = _get_client().audio.transcriptions.create(model=settings.whisper_model, file=audio)
    return (result.text or "").strip()


def transcribe_bytes(data: bytes, filename: str) -> str:
    """Transcribe audio uploaded by the browser (webm / ogg / mp4 / wav). The extension tells Whisper the format."""
    result = _get_client().audio.transcriptions.create(
        model=settings.whisper_model, file=(filename, data), language="en"
    )
    return (result.text or "").strip()
