"""Immutable configuration constants."""

SETTINGS_FILE   = "settings.json"
WHISPER_MODEL   = "mlx-community/whisper-large-v3-mlx"
TTS_MODEL       = "mlx-community/Kokoro-82M-bf16"
TTS_VOICE       = "af_heart"          # American female, natural tone
TTS_SPEED       = 1.0
TTS_SAMPLE_RATE = 24000               # Kokoro outputs at 24 kHz
TTS_BACKENDS    = ["kokoro", "say"]
SAY_VOICES      = ["Ava", "Samantha", "Daniel", "Karen", "Moira"]
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
    "Speak naturally as if having a conversation. "
    "Always reply in English. "
    "If a tool returns an error, a partial failure, or any message that looks "
    "like a problem (examples: 'failed', 'error', 'HTTP 4xx', 'HTTP 5xx', "
    "'transcription failed', 'not configured', 'timeout', 'forbidden'), do NOT "
    "hide it or smooth it over. Tell the user plainly what went wrong, quoting "
    "the error detail so they can act on it. It is better to report a failure "
    "than to pretend things worked."
)
