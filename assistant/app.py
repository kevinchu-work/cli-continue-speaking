"""VoiceAssistant — main application class, keyboard handling, and run loop."""

import os
import signal
import sys
import termios
import threading
import time

import mlx_whisper
import numpy as np
import sounddevice as sd
from google.genai import errors as genai_errors
from pynput import keyboard as kb

from .config import (
    MIC_SAMPLE_RATE, MIN_RECORD_SECS, TTS_BACKENDS, SAY_VOICES, WHISPER_MODEL,
)
from .llm import LLMClient
from .settings import Settings, load_settings
from .tts import TTSEngine


class VoiceAssistant:
    def __init__(self) -> None:
        self._settings = load_settings()
        self._cancel = threading.Event()
        self._tts = TTSEngine(self._settings, self._cancel)
        self._llm = LLMClient(self._settings)

        self._audio_chunks: list = []
        self._is_recording: bool = False

        # Preload both models so the first turn runs without any fetch delay
        self._tts.preload()
        self._preload_whisper()

    # ── Preload ───────────────────────────────────────────────────────────────

    def _preload_whisper(self) -> None:
        """Warm up the Whisper model with a silent dummy transcription."""
        print("Loading Whisper model...")
        silence = np.zeros(MIC_SAMPLE_RATE, dtype=np.float32)  # 1 s of silence
        mlx_whisper.transcribe(silence, path_or_hf_repo=WHISPER_MODEL)
        print("All models ready.\n")

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _mic_callback(self, indata, frames, time_info, status) -> None:
        if self._is_recording:
            self._audio_chunks.append(indata.copy())

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _process(self) -> None:
        """Transcribe buffered audio → LLM → speak response."""
        self._cancel.clear()

        if not self._audio_chunks:
            return

        audio = np.concatenate(self._audio_chunks).flatten().astype(np.float32)
        self._audio_chunks = []

        if len(audio) < MIC_SAMPLE_RATE * MIN_RECORD_SECS:
            print("(clip too short, ignored)\n")
            return

        print("Transcribing...", end=" ", flush=True)
        result = mlx_whisper.transcribe(audio, path_or_hf_repo=WHISPER_MODEL)

        if self._cancel.is_set():
            print("cancelled.\n")
            return

        user_text = result["text"].strip()
        if not user_text:
            print("(nothing heard)\n")
            return

        print(f"done.\nYou: {user_text}")
        print("Thinking...", end=" ", flush=True)

        try:
            response = self._llm.send(user_text)
        except genai_errors.APIError as e:
            # Transient Gemini/Gemma errors (500, 503, rate limits, etc.).
            # A failed turn can end up stuck in the chat's curated history
            # and poison every subsequent send — reset the session so the
            # next turn starts clean.  Conversation context is lost, which
            # beats an unusable loop.
            print(f"failed.\n[LLM error: {e.code} {e.status}] — resetting chat.\n")
            self._llm.reset_chat()
            self._tts.speak("Sorry, the model hiccuped. I've reset the chat, please try again.")
            return
        except Exception as e:
            print(f"failed.\n[Unexpected error: {e}] — resetting chat.\n")
            self._llm.reset_chat()
            self._tts.speak("Sorry, something went wrong.")
            return

        if self._cancel.is_set():
            print("cancelled.\n")
            return

        reply = response.text.strip()
        print("done.")
        print(f"Assistant: {reply}\n")
        self._tts.speak(reply)

    # ── Settings mutators ─────────────────────────────────────────────────────

    def _rotate_tts(self) -> None:
        self._settings.tts_idx = (self._settings.tts_idx + 1) % len(TTS_BACKENDS)
        self._settings.save()
        print(f"TTS → {TTS_BACKENDS[self._settings.tts_idx]}\n")

    def _adjust_tts_speed(self, delta: float) -> None:
        self._settings.tts_speed = round(
            max(0.5, min(2.0, self._settings.tts_speed + delta)), 2
        )
        self._settings.save()
        print(f"Speed → {self._settings.tts_speed}x\n")

    def _rotate_say_voice(self) -> None:
        self._settings.say_voice_idx = (self._settings.say_voice_idx + 1) % len(SAY_VOICES)
        self._settings.save()
        print(f"say voice → {SAY_VOICES[self._settings.say_voice_idx]}\n")

    def _toggle_continue_speaking(self) -> None:
        self._settings.continue_speaking = not self._settings.continue_speaking
        self._settings.save()
        state = "on" if self._settings.continue_speaking else "off"
        print(f"Continue speaking → {state}\n")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _print_banner(self) -> None:
        tts_label = TTS_BACKENDS[self._settings.tts_idx]
        if tts_label == "say":
            tts_label += f"  ({SAY_VOICES[self._settings.say_voice_idx]})"
        print("\n┌─────────────────────────────────────┐")
        print("│        Voice Assistant Ready        │")
        print("└─────────────────────────────────────┘")
        print(f"  Model      [ctrl+tab]    {self._llm.model_name}")
        print(f"  TTS        [ctrl+t,v]    {tts_label}")
        print(f"  Speed      [ctrl+↑↓]     {self._settings.tts_speed}x")
        print(f"  Continue   [ctrl+k]      {'on' if self._settings.continue_speaking else 'off'}")
        print()
        print("  space      start / stop recording")
        print("  esc        cancel")
        print("  ctrl+q     quit")
        print()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        space_down = threading.Event()
        space_up   = threading.Event()
        ctrl_held  = False

        def on_press(key):
            nonlocal ctrl_held

            if key in (kb.Key.ctrl_l, kb.Key.ctrl_r):
                ctrl_held = True
            elif key == kb.Key.tab and ctrl_held:
                self._llm.rotate_model()
            elif getattr(key, "char", None) == "t" and ctrl_held:
                self._rotate_tts()
            elif getattr(key, "char", None) == "k" and ctrl_held:
                self._toggle_continue_speaking()
                # If continue speaking was just turned off mid-recording, discard and don't send
                if not self._settings.continue_speaking and self._is_recording:
                    self._is_recording = False
                    self._audio_chunks = []
                    self._cancel.set()
                    sd.stop()
                    space_up.set()
                    print("Recording discarded.\n")
            elif key == kb.Key.up and ctrl_held:
                self._adjust_tts_speed(+0.05)
            elif key == kb.Key.down and ctrl_held:
                self._adjust_tts_speed(-0.05)
            elif getattr(key, "char", None) == "q" and ctrl_held:
                os.kill(os.getpid(), signal.SIGINT)
            elif getattr(key, "char", None) == "v" and ctrl_held:
                if TTS_BACKENDS[self._settings.tts_idx] == "say":
                    self._rotate_say_voice()
                else:
                    print("(Ctrl+V only applies to say backend)\n")
            elif key == kb.Key.space:
                if not self._is_recording:
                    self._cancel.clear()  # reset any prior cancel before a fresh recording
                    self._is_recording = True
                    self._audio_chunks = []
                    space_down.set()
                    print("🎙  Recording... (press SPACE again to send)")
                else:
                    self._is_recording = False
                    space_up.set()
            elif key == kb.Key.esc:
                # Cancel wherever we are: recording, transcribing, waiting for LLM, or speaking
                if self._is_recording:
                    self._is_recording = False
                    self._audio_chunks = []
                    space_up.set()
                self._cancel.set()
                sd.stop()
                print("Cancelled.\n")

        def on_release(key):
            nonlocal ctrl_held
            if key in (kb.Key.ctrl_l, kb.Key.ctrl_r):
                ctrl_held = False

        stream = sd.InputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._mic_callback,
        )

        self._print_banner()

        # Disable terminal echo so hotkey escape sequences (^[[1;5A etc.) don't
        # bleed into the output.  Restore unconditionally on exit.
        _fd: int | None = None
        _old_attrs = None
        if sys.stdin.isatty():
            _fd = sys.stdin.fileno()
            _old_attrs = termios.tcgetattr(_fd)
            new_attrs = list(_old_attrs)
            new_attrs[3] &= ~termios.ECHO   # clear ECHO flag in c_lflag
            termios.tcsetattr(_fd, termios.TCSANOW, new_attrs)

        try:
            with stream, kb.Listener(on_press=on_press, on_release=on_release):
                try:
                    auto_record = False
                    while True:
                        if auto_record:
                            self._is_recording = True
                            self._audio_chunks = []
                            auto_record = False
                            print("🎙  Recording... (press SPACE to send)")
                        else:
                            space_down.wait()
                            space_down.clear()

                        space_up.wait()
                        space_up.clear()

                        if not self._cancel.is_set():
                            self._process()
                            auto_record = self._settings.continue_speaking and not self._cancel.is_set()
                        else:
                            auto_record = False
                except KeyboardInterrupt:
                    print("\nGoodbye!")
        finally:
            if _fd is not None and _old_attrs is not None:
                termios.tcsetattr(_fd, termios.TCSADRAIN, _old_attrs)


def main_cli() -> None:
    """Entry point for `uv run assistant` / installed script."""
    from dotenv import load_dotenv
    load_dotenv()
    VoiceAssistant().run()
