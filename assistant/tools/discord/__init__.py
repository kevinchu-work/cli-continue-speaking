"""Discord tool — registered only when a webhook URL is configured.

Setup: see README.md in this folder.
"""

import os

from dotenv import load_dotenv

load_dotenv()

if os.environ.get("DISCORD_WEBHOOK_URL"):
    from .client import send_discord_message
    TOOLS = [send_discord_message]
else:
    TOOLS = []
