"""Text-to-speech engine supporting Kokoro (mlx-audio) and macOS say."""

import subprocess
import threading
import time

import numpy as np
import sounddevice as sd
from mlx_audio.tts.utils import load_model as load_tts

from .config import TTS_MODEL, TTS_VOICE, TTS_SAMPLE_RATE, TTS_BACKENDS, SAY_VOICES
from .settings import Settings


class TTSEngine:
    def __init__(self, settings: Settings, cancel: threading.Event) -> None:
        self._settings = settings
        self._cancel = cancel
        self._model = None  # lazy-loaded on first Kokoro use

    # ── Kokoro ────────────────────────────────────────────────────────────────

    def _get_model(self):
        if self._model is None:
            print("Loading Kokoro TTS model (first run downloads ~330 MB)...")
            self._model = load_tts(TTS_MODEL)
        return self._model

    def _speak_kokoro(self, text: str) -> None:
        parts = []
        for chunk in self._get_model().generate(
            text, voice=TTS_VOICE, speed=self._settings.tts_speed, lang_code="a"
        ):
            if self._cancel.is_set():
                return
            parts.append(chunk.audio)

        if parts and not self._cancel.is_set():
            audio = np.concatenate(parts).astype(np.float32)
            sd.play(audio, samplerate=TTS_SAMPLE_RATE)
            deadline = time.monotonic() + len(audio) / TTS_SAMPLE_RATE
            while time.monotonic() < deadline:
                if self._cancel.is_set():
                    sd.stop()
                    return
                time.sleep(0.05)

    # ── macOS say ─────────────────────────────────────────────────────────────

    def _speak_say(self, text: str) -> None:
        wpm = int(175 * self._settings.tts_speed)  # 175 WPM is macOS default
        voice = SAY_VOICES[self._settings.say_voice_idx]
        proc = subprocess.Popen(["say", "-v", voice, "-r", str(wpm), text])
        while proc.poll() is None:
            if self._cancel.is_set():
                proc.terminate()
                return
            time.sleep(0.05)

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        if TTS_BACKENDS[self._settings.tts_idx] == "kokoro":
            self._speak_kokoro(text)
        else:
            self._speak_say(text)
