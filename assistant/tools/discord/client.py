"""Discord client — send messages via an incoming webhook (no bot required)."""

import json
import os
import urllib.request


def send_discord_message(message: str) -> str:
    """Post a message to the configured Discord channel.

    Args:
        message: Text content to post (up to 2000 characters).

    Returns:
        Confirmation or an error description.
    """
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        return "Discord is not configured — set DISCORD_WEBHOOK_URL in .env."

    payload = json.dumps({"content": message[:2000]}).encode()
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={
            "Content-Type": "application/json",
            # Discord's Cloudflare layer blocks the default Python-urllib UA
            # with error 1010.  Per Discord docs, clients must supply a UA
            # matching: "DiscordBot (URL, Version)".
            "User-Agent": "DiscordBot (https://github.com/kevin/v-to-work, 0.1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return "Message posted to Discord."
            return f"Discord returned status {resp.status}."
    except Exception as e:
        return f"Failed to post to Discord: {e}"
