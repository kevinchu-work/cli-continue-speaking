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

WHISPER_MODEL   = "mlx-community/whisper-large-v3-mlx"  # change to whisper-small-mlx for faster/lighter
TTS_MODEL       = "mlx-community/Kokoro-82M-bf16"
TTS_VOICE       = "af_heart"          # American female, natural tone
TTS_SPEED       = 1.0
TTS_SAMPLE_RATE = 24000               # Kokoro outputs at 24 kHz
GEMINI_MODEL    = "gemini-2.0-flash"
MIC_SAMPLE_RATE = 16000               # Whisper expects 16 kHz
MIN_RECORD_SECS = 0.4                 # ignore recordings shorter than this

SYSTEM_PROMPT = (
    "You are a helpful voice assistant. "
    "Keep your responses concise and conversational — they will be spoken aloud. "
    "Do not use markdown, bullet points, asterisks, or any special formatting. "
    "Speak naturally as if having a conversation."
)

# ── Startup ───────────────────────────────────────────────────────────────────

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    sys.exit("Error: GOOGLE_API_KEY not set. Copy .env.example to .env and add your key.")

print("Initialising Gemini...")
client = genai.Client(api_key=api_key)
chat = client.chats.create(
    model=GEMINI_MODEL,
    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
)

print("Loading Kokoro TTS model (first run downloads ~330 MB)...")
tts_model = load_tts(TTS_MODEL)

print("Whisper will load on first transcription.\n")

# ── Audio helpers ─────────────────────────────────────────────────────────────

_audio_chunks: list = []
_is_recording: bool = False
_cancel = threading.Event()        # set by Escape to abort the current pipeline


def _mic_callback(indata, frames, time_info, status):
    """Called continuously by sounddevice while the stream is open."""
    if _is_recording:
        _audio_chunks.append(indata.copy())


def speak(text: str):
    """Convert text to speech via Kokoro and play through speakers."""
    parts = []
    for chunk in tts_model.generate(text, voice=TTS_VOICE, speed=TTS_SPEED, lang_code="a"):
        if _cancel.is_set():
            return
        parts.append(chunk.audio)
    if parts and not _cancel.is_set():
        audio = np.concatenate(parts).astype(np.float32)
        sd.play(audio, samplerate=TTS_SAMPLE_RATE)
        # Poll so Escape can cut playback short
        duration = len(audio) / TTS_SAMPLE_RATE
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if _cancel.is_set():
                sd.stop()
                return
            time.sleep(0.05)


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


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    global _is_recording, _audio_chunks

    space_down  = threading.Event()
    space_up    = threading.Event()

    def on_press(key):
        global _is_recording, _audio_chunks
        if key == kb.Key.space and not _is_recording:
            _is_recording = True
            _audio_chunks = []
            space_down.set()
            print("🎙  Recording... (release SPACE to send)")
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
        global _is_recording
        if key == kb.Key.space and _is_recording:
            _is_recording = False
            space_up.set()

    stream = sd.InputStream(
        samplerate=MIC_SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=_mic_callback,
    )

    print("=== Voice Assistant Ready ===")
    print("Hold SPACE to speak, release to send.  ESC to cancel.  Ctrl+C to quit.\n")

    with stream, kb.Listener(on_press=on_press, on_release=on_release):
        try:
            while True:
                space_down.wait()
                space_down.clear()
                space_up.wait()
                space_up.clear()
                if not _cancel.is_set():
                    process()
        except KeyboardInterrupt:
            print("\nGoodbye!")


if __name__ == "__main__":
    main()
