"""Speech in, speech out.

STT: ElevenLabs Scribe if ELEVENLABS_API_KEY is set, otherwise the free
     Google recogniser bundled with the SpeechRecognition library.
TTS: ElevenLabs. If no key / any failure, returns None and the app just
     shows text - the demo keeps going.
"""
from __future__ import annotations

import io
import os

import requests

ELEVEN_BASE = "https://api.elevenlabs.io/v1"
# "Rachel" - a calm, warm default voice. Override with ELEVENLABS_VOICE_ID.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def _eleven_key() -> str | None:
    return os.getenv("ELEVENLABS_API_KEY") or None


def transcribe(wav_bytes: bytes) -> str:
    """Turn recorded audio into text. Raises RuntimeError with a friendly message on failure."""
    key = _eleven_key()
    if key:
        try:
            r = requests.post(
                f"{ELEVEN_BASE}/speech-to-text",
                headers={"xi-api-key": key},
                data={"model_id": "scribe_v1"},
                files={"file": ("answer.wav", wav_bytes, "audio/wav")},
                timeout=30,
            )
            r.raise_for_status()
            text = (r.json().get("text") or "").strip()
            if text:
                return text
        except requests.RequestException:
            pass  # fall through to the free recogniser

    try:
        import speech_recognition as sr
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("SpeechRecognition is not installed.") from e

    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError as e:
        raise RuntimeError("Couldn't make out any words - try again a little closer to the mic.") from e
    except sr.RequestError as e:
        raise RuntimeError(f"Speech service unavailable: {e}") from e


def speak(text: str) -> bytes | None:
    """Return MP3 bytes for `text`, or None if TTS isn't available."""
    key = _eleven_key()
    if not key or not text.strip():
        return None
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    try:
        r = requests.post(
            f"{ELEVEN_BASE}/text-to-speech/{voice_id}",
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={
                "text": text,
                "model_id": os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.content
    except requests.RequestException:
        return None
