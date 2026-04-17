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

    def reset_chat(self) -> None:
        """Drop conversation history and start a fresh chat session.

        Called after an API error so a failed turn stuck in curated history
        doesn't poison every subsequent request.
        """
        self._chat = self._new_chat()

    def send(self, text: str):
        return self._chat.send_message(text)

    def draft_reply(self, incoming: str) -> str:
        """One-shot draft of a Discord reply to an incoming message.

        Deliberately does NOT use the voice-chat session — auto-replies
        shouldn't pollute conversational history, and the voice system
        prompt's "speak aloud, no formatting" rules are wrong here.
        Returns the bare reply text ready to post.
        """
        system = (
            "You are drafting a short, casual Discord reply on the user's "
            "behalf.  Write only the reply text — no quotes, no preamble, "
            "no 'Sure, here's a reply:'.  One or two sentences.  Match the "
            "tone of the incoming message.  Plain text only — no markdown."
        )
        resp = self._client.models.generate_content(
            model=self.model_name,
            contents=f"Incoming message:\n{incoming}\n\nYour reply:",
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return (resp.text or "").strip()
