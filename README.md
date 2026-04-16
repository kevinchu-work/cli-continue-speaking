# Voice Assistant

Mic → **mlx-whisper** (STT) → **Gemma 4 via Gemini API** (LLM, with tool use) → **Kokoro** (TTS)

STT and TTS run fully on-device. Only the LLM call hits the network.

---

## Setup

**1. Install dependencies**

```bash
uv sync
```

> Whisper (~3 GB) and Kokoro (~330 MB) download on first launch and are cached.

**2. Configure API keys**

```bash
cp .env.example .env
# edit .env — only GOOGLE_API_KEY is required
```

Grab a free key at [aistudio.google.com](https://aistudio.google.com). Gemma 4 is free-tier and generous.

**3. Run**

```bash
uv run main.py
```

First launch preloads both models (~15 s) so every turn after that is instant.

---

## Usage

| Key | Action |
|---|---|
| `space` | Press to start recording; press again to send |
| `esc` | Cancel current recording / transcription / response |
| `ctrl+tab` | Rotate LLM model (Gemma 4 26B MoE ↔ 31B Dense) |
| `ctrl+t` | Toggle TTS backend (Kokoro ↔ macOS `say`) |
| `ctrl+v` | Cycle `say` voices (Ava, Samantha, Daniel, Karen, Moira) |
| `ctrl+↑` / `ctrl+↓` | Adjust TTS speed (0.5x – 2.0x, 0.05 step) |
| `ctrl+k` | Toggle "continue speaking" — auto-records again after each reply |
| `ctrl+q` | Quit |

All settings persist to `settings.json` between runs.

---

## Tools

The LLM can call Python functions to take actions. Tools **auto-register** when their setup is present, so if you haven't configured Gmail the LLM won't try to send email.

| Tool | Setup | Capability |
|---|---|---|
| `get_datetime` | none | "What time is it?" |
| `open_application` | none | "Open Safari" |
| `web_search` | see [`tools/search/README.md`](assistant/tools/search/README.md) | Current events, weather, prices, news |
| `send_discord_message` | see [`tools/discord/README.md`](assistant/tools/discord/README.md) | Post to a Discord channel |
| `send_email` | see [`tools/gmail/README.md`](assistant/tools/gmail/README.md) | Send email via Gmail |

The LLM can chain multiple tool calls in one turn — e.g. *"what time is it then email that to alice@x.com"* runs `get_datetime()` and `send_email(...)` back-to-back.

### Adding your own tool

Each tool is a Python function with a clear docstring. Drop a new folder under `assistant/tools/<name>/` with an `__init__.py` that exports a `TOOLS = [...]` list, and register it in `assistant/tools/__init__.py`. See the existing sub-folders as templates.

---

## Layout

```
assistant/
├── config.py     # constants (models, sample rates, prompt)
├── settings.py   # persisted preferences
├── llm.py        # Gemini chat client
├── tts.py        # Kokoro + `say` backends
├── tools/        # LLM-callable tools (self-contained sub-packages)
│   ├── core.py
│   ├── search/
│   ├── gmail/
│   └── discord/
└── app.py        # VoiceAssistant class, keyboard, run loop
main.py           # entry point
```

---

## Pipeline latency (M5, 32 GB)

| Step | Approx. time |
|---|---|
| Whisper transcription | ~1 s |
| Gemini API response | ~1–2 s |
| Kokoro TTS generation | ~0.5 s |
| **Total per turn** | **~2–4 s** |

Models are preloaded at startup, so the first turn has no extra cost.
