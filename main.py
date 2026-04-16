#!/usr/bin/env python3
"""Entry point for the voice assistant."""

from dotenv import load_dotenv

load_dotenv()

from assistant.app import VoiceAssistant


def main() -> None:
    VoiceAssistant().run()


if __name__ == "__main__":
    main()
