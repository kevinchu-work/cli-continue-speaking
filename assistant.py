#!/usr/bin/env python3
"""
Voice Assistant
  Mic → mlx-whisper (STT) → Gemini (LLM) → Kokoro/mlx-audio (TTS)

Usage:
  Hold SPACE to record your voice, release to send.
  Press Ctrl+C to quit.
"""

import os
import sys
import signal
import json
import subprocess
import threading
import time
import numpy as np
import sounddevice as sd
import mlx_whisper
from mlx_audio.tts.utils import load_model as load_tts
from google import genai
from google.genai import types
from pynput import keyboard as kb
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

SETTINGS_FILE   = "settings.json"
WHISPER_MODEL   = "mlx-community/whisper-large-v3-mlx"  # change to whisper-small-mlx for faster/lighter
TTS_MODEL       = "mlx-community/Kokoro-82M-bf16"
TTS_VOICE       = "af_heart"          # American female, natural tone
TTS_SPEED       = 1.0
TTS_SAMPLE_RATE = 24000               # Kokoro outputs at 24 kHz
TTS_BACKENDS    = ["kokoro", "say"]   # Ctrl+T to toggle at runtime
SAY_VOICES      = ["Ava", "Samantha", "Daniel", "Karen", "Moira"]  # Ctrl+V to cycle (say only)
MODELS = [
    "gemma-4-26b-a4b-it",   # MoE — fast (only 4B active params)
    "gemma-4-31b-it",       # Dense — more capable
]
MIC_SAMPLE_RATE = 16000               # Whisper expects 16 kHz
MIN_RECORD_SECS = 0.4                 # ignore recordings shorter than this

SYSTEM_PROMPT = (
    "You are a helpful voice assistant. "
    "Keep your responses concise and conversational — they will be spoken aloud. "
    "Do not use markdown, bullet points, asterisks, or any special formatting. "
    "Speak naturally as if having a conversation."
    "Always reply in English. "
)

# ── Settings persistence ──────────────────────────────────────────────────────

def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "model_idx":         _model_idx,
            "tts_idx":           _tts_idx,
            "say_voice_idx":     _say_voice_idx,
            "tts_speed":         _tts_speed,
            "continue_speaking": _continue_speaking,
        }, f, indent=2)

# ── State ─────────────────────────────────────────────────────────────────────

_settings = load_settings()

_audio_chunks: list = []
_is_recording: bool = False
_cancel = threading.Event()        # set by Escape to abort the current pipeline
_model_idx: int = min(_settings.get("model_idx", 0), len(MODELS) - 1)
_tts_idx: int = min(_settings.get("tts_idx", 0), len(TTS_BACKENDS) - 1)
_say_voice_idx: int = min(_settings.get("say_voice_idx", 0), len(SAY_VOICES) - 1)
_tts_model = None                  # lazy-loaded on first Kokoro use
_tts_speed: float = round(max(0.5, min(2.0, _settings.get("tts_speed", 1.0))), 1)
_continue_speaking: bool = _settings.get("continue_speaking", False)

# ── Startup ───────────────────────────────────────────────────────────────────

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    sys.exit("Error: GOOGLE_API_KEY not set. Copy .env.example to .env and add your key.")

print(f"Initialising Gemini (model: {MODELS[_model_idx]})...")
client = genai.Client(api_key=api_key)

def _new_chat(model_id: str):
    return client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )

chat = _new_chat(MODELS[_model_idx])

print("Whisper and Kokoro will load on first use.\n")

# ── Audio helpers ─────────────────────────────────────────────────────────────


def _mic_callback(indata, frames, time_info, status):
    """Called continuously by sounddevice while the stream is open."""
    if _is_recording:
        _audio_chunks.append(indata.copy())


def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        print("Loading Kokoro TTS model (first run downloads ~330 MB)...")
        _tts_model = load_tts(TTS_MODEL)
    return _tts_model


def _speak_kokoro(text: str):
    parts = []
    for chunk in _get_tts_model().generate(text, voice=TTS_VOICE, speed=_tts_speed, lang_code="a"):
        if _cancel.is_set():
            return
        parts.append(chunk.audio)
    if parts and not _cancel.is_set():
        audio = np.concatenate(parts).astype(np.float32)
        sd.play(audio, samplerate=TTS_SAMPLE_RATE)
        deadline = time.monotonic() + len(audio) / TTS_SAMPLE_RATE
        while time.monotonic() < deadline:
            if _cancel.is_set():
                sd.stop()
                return
            time.sleep(0.05)


def _speak_say(text: str):
    wpm = int(175 * _tts_speed)   # 175 WPM is macOS default
    proc = subprocess.Popen(["say", "-v", SAY_VOICES[_say_voice_idx], "-r", str(wpm), text])
    while proc.poll() is None:
        if _cancel.is_set():
            proc.terminate()
            return
        time.sleep(0.05)


def speak(text: str):
    if TTS_BACKENDS[_tts_idx] == "kokoro":
        _speak_kokoro(text)
    else:
        _speak_say(text)


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process():
    """Transcribe buffered audio → Gemini → speak response."""
    global _audio_chunks
    _cancel.clear()

    if not _audio_chunks:
        return

    audio = np.concatenate(_audio_chunks).flatten().astype(np.float32)
    _audio_chunks = []

    if len(audio) < MIC_SAMPLE_RATE * MIN_RECORD_SECS:
        print("(clip too short, ignored)\n")
        return

    print("Transcribing...", end=" ", flush=True)
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=WHISPER_MODEL)

    if _cancel.is_set():
        print("cancelled.\n")
        return

    user_text = result["text"].strip()
    if not user_text:
        print("(nothing heard)\n")
        return

    print(f"done.\nYou: {user_text}")
    print("Thinking...", end=" ", flush=True)

    response = chat.send_message(user_text)

    if _cancel.is_set():
        print("cancelled.\n")
        return

    reply = response.text.strip()
    print("done.")

    print(f"Assistant: {reply}\n")
    speak(reply)


# ── Model / TTS rotation ──────────────────────────────────────────────────────

def rotate_tts():
    global _tts_idx
    _tts_idx = (_tts_idx + 1) % len(TTS_BACKENDS)
    save_settings()
    print(f"TTS → {TTS_BACKENDS[_tts_idx]}\n")


def adjust_tts_speed(delta: float):
    global _tts_speed
    _tts_speed = round(max(0.5, min(2.0, _tts_speed + delta)), 2)
    save_settings()
    print(f"Speed → {_tts_speed}x\n")


def rotate_say_voice():
    global _say_voice_idx
    _say_voice_idx = (_say_voice_idx + 1) % len(SAY_VOICES)
    save_settings()
    print(f"say voice → {SAY_VOICES[_say_voice_idx]}\n")


def toggle_continue_speaking():
    global _continue_speaking
    _continue_speaking = not _continue_speaking
    save_settings()
    print(f"Continue speaking → {'on' if _continue_speaking else 'off'}\n")


def rotate_model():
    global chat, _model_idx
    _model_idx = (_model_idx + 1) % len(MODELS)
    model_id = MODELS[_model_idx]
    chat = _new_chat(model_id)
    save_settings()
    print(f"Model → {model_id}\n")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    global _is_recording, _audio_chunks

    space_down   = threading.Event()
    space_up     = threading.Event()
    _ctrl_held   = False

    def on_press(key):
        nonlocal _ctrl_held
        global _is_recording, _audio_chunks

        if key in (kb.Key.ctrl_l, kb.Key.ctrl_r):
            _ctrl_held = True
        elif key == kb.Key.tab and _ctrl_held:
            rotate_model()
        elif getattr(key, 'char', None) == 't' and _ctrl_held:
            rotate_tts()
        elif getattr(key, 'char', None) == 'k' and _ctrl_held:
            toggle_continue_speaking()
            # If we just turned it off mid-recording, discard and don't send
            if not _continue_speaking and _is_recording:
                _is_recording = False
                _audio_chunks = []
                _cancel.set()
                sd.stop()
                space_up.set()
                print("Recording discarded.\n")
        elif key == kb.Key.up and _ctrl_held:
            adjust_tts_speed(+0.05)
        elif key == kb.Key.down and _ctrl_held:
            adjust_tts_speed(-0.05)
        elif getattr(key, 'char', None) == 'q' and _ctrl_held:
            os.kill(os.getpid(), signal.SIGINT)
        elif getattr(key, 'char', None) == 'v' and _ctrl_held:
            if TTS_BACKENDS[_tts_idx] == "say":
                rotate_say_voice()
            else:
                print("(Ctrl+V only applies to say backend)\n")
        elif key == kb.Key.space:
            if not _is_recording:
                _is_recording = True
                _audio_chunks = []
                space_down.set()
                print("🎙  Recording... (press SPACE again to send)")
            else:
                _is_recording = False
                space_up.set()
        elif key == kb.Key.esc:
            # Cancel wherever we are: recording, transcribing, waiting for LLM, or speaking
            if _is_recording:
                _is_recording = False
                _audio_chunks = []
                space_up.set()   # unblock the space_up.wait() in the main loop
            _cancel.set()
            sd.stop()            # cut any ongoing playback immediately
            print("Cancelled.\n")

    def on_release(key):
        nonlocal _ctrl_held
        global _is_recording

        if key in (kb.Key.ctrl_l, kb.Key.ctrl_r):
            _ctrl_held = False

    stream = sd.InputStream(
        samplerate=MIC_SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=_mic_callback,
    )

    tts_label = TTS_BACKENDS[_tts_idx]
    if tts_label == "say":
        tts_label += f"  ({SAY_VOICES[_say_voice_idx]})"
    print("\n┌─────────────────────────────────────┐")
    print("│        Voice Assistant Ready        │")
    print("└─────────────────────────────────────┘")
    print(f"  Model      [ctrl+tab]    {MODELS[_model_idx]}")
    print(f"  TTS        [ctrl+t,v]    {tts_label}")
    print(f"  Speed      [ctrl+↑↓]     {_tts_speed}x")
    print(f"  Continue   [ctrl+k]      {'on' if _continue_speaking else 'off'}")
    print()
    print(f"  space      start / stop recording")
    print(f"  esc        cancel")
    print(f"  ctrl+q     quit")
    print()

    with stream, kb.Listener(on_press=on_press, on_release=on_release):
        try:
            _auto_record = False
            while True:
                if _auto_record:
                    _is_recording = True
                    _audio_chunks = []
                    _auto_record = False
                    print("🎙  Recording... (press SPACE to send)")
                else:
                    space_down.wait()
                    space_down.clear()

                space_up.wait()
                space_up.clear()

                if not _cancel.is_set():
                    process()
                    _auto_record = _continue_speaking and not _cancel.is_set()
                else:
                    _auto_record = False
        except KeyboardInterrupt:
            print("\nGoodbye!")


if __name__ == "__main__":
    main()
