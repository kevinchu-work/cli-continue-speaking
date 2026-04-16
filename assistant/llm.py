"""LLM client wrapping the Google Gemini/Gemma API."""

import os
import sys

from google import genai
from google.genai import types

from .config import MODELS, SYSTEM_PROMPT
from .settings import Settings
from .tools import TOOLS


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            sys.exit("Error: GOOGLE_API_KEY not set. Copy .env.example to .env and add your key.")

        print(f"Initialising Gemini (model: {self.model_name})...")
        self._client = genai.Client(api_key=api_key)
        self._chat = self._new_chat()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return MODELS[self._settings.model_idx]

    def _new_chat(self):
        return self._client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=TOOLS,
            ),
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def rotate_model(self) -> None:
        self._settings.model_idx = (self._settings.model_idx + 1) % len(MODELS)
        self._settings.save()
        self._chat = self._new_chat()
        print(f"Model → {self.model_name}\n")

    def send(self, text: str):
        return self._chat.send_message(text)
