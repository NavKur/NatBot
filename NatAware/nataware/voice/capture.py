"""Microphone capture with webrtcvad voice-activity detection.

Records from the default input device, waits for the user to start talking, and stops
once `silence_seconds` of continuous non-speech is detected. The utterance is buffered
to a temporary 16 kHz mono 16-bit .wav file (the format both webrtcvad and Whisper like).
"""

from __future__ import annotations

import collections
import tempfile
import time
import wave
from pathlib import Path

from nataware.config import settings

SAMPLE_RATE = 16_000  # webrtcvad supports 8/16/32/48 kHz
FRAME_MS = 30  # webrtcvad supports 10/20/30 ms frames
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
SAMPLE_WIDTH = 2  # int16


def record_utterance(
    silence_seconds: float | None = None,
    aggressiveness: int | None = None,
    start_timeout: float = 30.0,
    max_seconds: float = 90.0,
    trigger_window_ms: int = 300,
    trigger_ratio: float = 0.6,
) -> Path | None:
    """Block until one utterance is captured. Returns the .wav path, or None on timeout."""
    import sounddevice as sd  # imported lazily so the API/tests don't need PortAudio
    import webrtcvad

    silence_seconds = settings.vad_silence_seconds if silence_seconds is None else silence_seconds
    aggressiveness = settings.vad_aggressiveness if aggressiveness is None else aggressiveness

    vad = webrtcvad.Vad(aggressiveness)
    silence_frames_to_stop = max(1, int(silence_seconds * 1000 / FRAME_MS))
    max_frames = int(max_seconds * 1000 / FRAME_MS)

    # Ring buffer of recent frames: debounces the speech trigger (a cough or a click
    # shouldn't start a recording) and doubles as pre-roll so the first syllable isn't clipped.
    window: collections.deque[tuple[bytes, bool]] = collections.deque(maxlen=max(1, trigger_window_ms // FRAME_MS))
    voiced_frames: list[bytes] = []
    triggered = False
    silent_run = 0
    started_at = time.monotonic()

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, channels=1, dtype="int16") as stream:
        while True:
            data, _overflowed = stream.read(FRAME_SAMPLES)
            frame = bytes(data)
            is_speech = vad.is_speech(frame, SAMPLE_RATE)

            if not triggered:
                window.append((frame, is_speech))
                if sum(1 for _, s in window if s) > trigger_ratio * window.maxlen:
                    triggered = True
                    voiced_frames.extend(f for f, _ in window)
                    window.clear()
                elif time.monotonic() - started_at > start_timeout:
                    return None
                continue

            voiced_frames.append(frame)
            silent_run = 0 if is_speech else silent_run + 1
            if silent_run >= silence_frames_to_stop or len(voiced_frames) >= max_frames:
                break

    # Drop most of the trailing silence, keeping ~300 ms for a natural cut-off.
    keep_tail = min(silent_run, 10)
    if silent_run > keep_tail:
        voiced_frames = voiced_frames[: len(voiced_frames) - (silent_run - keep_tail)]

    return _write_wav(b"".join(voiced_frames))


def _write_wav(pcm: bytes) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix="nataware_utterance_", suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return Path(tmp.name)
