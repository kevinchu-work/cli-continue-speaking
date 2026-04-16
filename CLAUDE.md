# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                  # install runtime deps
uv sync --extra gmail    # also install Gmail tool deps (google-api-python-client, etc.)
uv run main.py           # launch the voice assistant
```

There is no test suite, linter, or formatter configured. `pyproject.toml` uses hatchling as the build backend with `packages = ["assistant"]`; the top-level `v-to-work` project name does not match the package dir, so that explicit hint is required.

## Architecture

Single-process voice pipeline: **mic → mlx-whisper (STT) → Gemini/Gemma 4 (LLM + tools) → Kokoro or macOS `say` (TTS)**. STT and TTS run on-device; only the LLM call hits the network. The user drives the turn with `space` (press to start/stop recording) and `esc` (cancel at any stage).

### Control flow and cancellation

`assistant/app.py` owns a single `threading.Event` named `_cancel` that every long-running stage polls. The mic callback and pynput keyboard listener fire on background threads; the main loop blocks on two events (`space_down`, `space_up`) to coordinate recording boundaries.

Critical invariant: `_cancel` must be **cleared** before each new user turn. It is cleared in two places:
- `_process()` entry (normal flow)
- `on_press(Space)` when starting a fresh recording (covers the path where a recording is discarded mid-stream by Ctrl+K and `_process` never runs)

If you add a new path that discards a turn, make sure the next recording still clears `_cancel` or the user's audio will be silently dropped.

Terminal echo is disabled via `termios.ECHO` during `run()` so hotkey escape sequences (`^[[1;5A`, `^K`, etc.) don't bleed into the transcript; it is restored in a `finally` block.

### Model preloading

Both Whisper and Kokoro are heavy and lazy by default — first-use loads cause a noticeable mid-conversation pause (seen as "Fetching N files" from HuggingFace). `VoiceAssistant.__init__` preloads both:
- `TTSEngine.preload()` calls `load_tts()` **and** runs a dummy `generate(".")` — the pipeline (language-specific vocoder, voice weights) initialises lazily on the first generate, so merely loading the model is not enough.
- `_preload_whisper()` runs `transcribe()` on 1 s of silence.

If you add a new ML component, give it an explicit preload hook and call it from `VoiceAssistant.__init__`.

### Tool system

LLM-callable tools live under `assistant/tools/<name>/` — each sub-package is self-contained (`client.py`, `__init__.py`, `README.md`) and **auto-disables when its prerequisites are missing** (env var unset, credentials file absent, optional deps not installed). `assistant/tools/__init__.py` aggregates `TOOLS` lists from every sub-package. The LLM only sees tools the user has actually configured, so there are no runtime errors for missing setup and no confusing "I can't do X" replies for capabilities the user never enabled.

The search tool has a further internal abstraction: `tools/search/providers/<name>.py` each expose `NAME`, `ENV_KEY`, and `search(query) -> str`. `client.py` picks the provider via `SEARCH_PROVIDER` env var or the first configured one in `providers/__init__.py::ALL`. Adding a new search backend is a single new file in `providers/` plus one import — no changes to the tool's LLM-facing contract.

**To add a new tool category**: copy the shape of `tools/discord/` (simplest — no OAuth, no optional deps), create `TOOLS = [...]` guarded by the relevant config check, and add one import line to `tools/__init__.py`.

### Settings and persistence

`assistant/settings.py` defines a `Settings` dataclass persisted to `settings.json` (cwd-relative, gitignored). Loaded once at startup; every mutator in `app.py` calls `self._settings.save()` immediately. Clamping and rounding happen **on load** so invalid values in settings.json are coerced quietly. The TTS speed adjust and load both use `round(..., 2)` — keep these precisions matched or stored values get silently rounded on next launch.

### LLM client

`assistant/llm.py` wraps `google.genai.Client` with `chats.create(tools=TOOLS)` for automatic function calling. The chat session holds history across turns within a run but is recreated on model rotation (`Ctrl+Tab`). Models listed in `assistant/config.py::MODELS` — currently Gemma 4 variants. The system prompt (also in `config.py`) instructs against markdown/formatting because everything gets spoken aloud.
