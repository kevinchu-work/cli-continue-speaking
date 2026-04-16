"""Discord tools — webhook (write) and bot (read) register independently.

Each is controlled by its own env var, so the user can enable one, both, or
neither.  Setup: see README.md in this folder.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TOOLS: list = []

# Webhook → send_discord_message (write, no bot needed)
if os.environ.get("DISCORD_WEBHOOK_URL"):
    from .client import send_discord_message
    TOOLS.append(send_discord_message)

# Bot token → read_discord_messages (needs a channel to read from — either
# DISCORD_CHANNEL_ID or the webhook's channel, resolved lazily)
if os.environ.get("DISCORD_BOT_TOKEN") and (
    os.environ.get("DISCORD_CHANNEL_ID") or os.environ.get("DISCORD_WEBHOOK_URL")
):
    from .bot import read_discord_messages
    TOOLS.append(read_discord_messages)
