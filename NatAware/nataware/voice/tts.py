"""Text-to-speech via ElevenLabs, played straight to the default output device.

Sentences are queued as soon as the LLM produces them. A background thread streams each
one from ElevenLabs as raw 16-bit PCM and writes the bytes to the sound card as they
arrive, so the user hears the first sentence while Claude is still generating the rest.
"""

from __future__ import annotations

import logging
import queue
import threading

import httpx

from nataware.config import settings

log = logging.getLogger(__name__)

PCM_SAMPLE_RATE = 22_050
_OUTPUT_FORMAT = f"pcm_{PCM_SAMPLE_RATE}"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


class Speaker:
    """Queue sentences with `say()`; call `wait()` before listening to the mic again."""

    def __init__(self) -> None:
        if not settings.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set (needed for TTS). Run with --no-tts to skip audio.")
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._http = httpx.Client(timeout=httpx.Timeout(30.0, read=60.0))
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="natbot-tts", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)
        if self._error:
            raise RuntimeError(f"Could not open the audio output device: {self._error}")

    def say(self, text: str) -> None:
        if text.strip():
            self._queue.put(text)

    def wait(self) -> None:
        """Block until everything queued so far has finished playing."""
        self._queue.join()

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=5)
        self._http.close()

    # ------------------------------------------------------------------ internals
    def _run(self) -> None:
        try:
            import sounddevice as sd

            # Constructing the stream opens the device; `with out:` below starts it.
            out = sd.RawOutputStream(samplerate=PCM_SAMPLE_RATE, channels=1, dtype="int16")
        except Exception as exc:  # surface device errors to the constructor
            self._error = exc
            self._ready.set()
            return
        self._ready.set()

        with out:
            while True:
                item = self._queue.get()
                try:
                    if item is None:
                        return
                    self._stream_and_play(item, out)
                except Exception:  # keep the conversation alive if one sentence fails
                    log.exception("TTS failed for sentence: %r", item)
                finally:
                    self._queue.task_done()

    def _stream_and_play(self, text: str, out) -> None:
        url = _TTS_URL.format(voice_id=settings.elevenlabs_voice_id)
        with self._http.stream(
            "POST",
            url,
            params={"output_format": _OUTPUT_FORMAT},
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={"text": text, "model_id": settings.elevenlabs_model},
        ) as resp:
            if resp.status_code >= 400:
                resp.read()
                raise RuntimeError(f"ElevenLabs {resp.status_code}: {resp.text[:300]}")
            leftover = b""
            for chunk in resp.iter_bytes():
                data = leftover + chunk
                usable = len(data) - (len(data) % 2)  # int16 samples are 2 bytes each
                if usable:
                    out.write(data[:usable])
                leftover = data[usable:]
