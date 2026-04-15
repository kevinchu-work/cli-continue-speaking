# Voice Assistant

Mic → **mlx-whisper** (STT) → **Gemini** (LLM) → **Kokoro** (TTS)

Runs fully on your Mac. Only the LLM call hits the network.

## Setup

**1. Install dependencies**

```bash
uv sync
```

> `mlx-whisper` and `mlx-audio` will download their models (~1 GB total) on first use.

**2. Add your Google AI Studio key**

```bash
cp .env.example .env
# edit .env and paste your GOOGLE_API_KEY
```

Get a free key at [aistudio.google.com](https://aistudio.google.com).

**3. Run**

```bash
uv run assistant.py
```

## Usage

| Action | Result |
|---|---|
| Hold `Space` | Records your voice |
| Release `Space` | Sends to Gemini, speaks the reply |
| `Ctrl+C` | Quit |

## Tuning

Edit the config block at the top of `assistant.py`:

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL` | `whisper-large-v3-mlx` | Swap to `whisper-small-mlx` for faster/lighter |
| `TTS_VOICE` | `af_heart` | Other voices: `af_bella`, `af_nova`, `am_adam`, `bm_george` |
| `TTS_SPEED` | `1.0` | Increase for faster speech |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Swap to `gemini-1.5-pro` for more capable responses |

## Pipeline latency (M5, 32 GB)

| Step | Approx. time |
|---|---|
| Whisper transcription | ~1 s |
| Gemini API response | ~1–2 s |
| Kokoro TTS generation | ~0.5 s |
| **Total per turn** | **~2–4 s** |
