"""Settings persistence — load from and save to settings.json."""

import json
from dataclasses import dataclass

from .config import MODELS, TTS_BACKENDS, SAY_VOICES, SETTINGS_FILE, TTS_SPEED


@dataclass
class Settings:
    model_idx: int = 0
    tts_idx: int = 0
    say_voice_idx: int = 0
    tts_speed: float = TTS_SPEED
    continue_speaking: bool = False

    def save(self) -> None:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "model_idx":         self.model_idx,
                "tts_idx":           self.tts_idx,
                "say_voice_idx":     self.say_voice_idx,
                "tts_speed":         self.tts_speed,
                "continue_speaking": self.continue_speaking,
            }, f, indent=2)


def load_settings() -> Settings:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return Settings()

    return Settings(
        model_idx=min(data.get("model_idx", 0), len(MODELS) - 1),
        tts_idx=min(data.get("tts_idx", 0), len(TTS_BACKENDS) - 1),
        say_voice_idx=min(data.get("say_voice_idx", 0), len(SAY_VOICES) - 1),
        tts_speed=round(max(0.5, min(2.0, data.get("tts_speed", TTS_SPEED))), 2),
        continue_speaking=data.get("continue_speaking", False),
    )
