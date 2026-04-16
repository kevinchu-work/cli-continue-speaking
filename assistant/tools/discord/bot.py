"""Discord bot client — read channel messages via the REST API.

Unlike webhooks (write-only, single channel, no identity), a bot token gives
the assistant a real Discord identity with channel-read permissions.
"""

import json
import os
import urllib.error
import urllib.request

_UA = "DiscordBot (https://github.com/kevin/v-to-work, 0.1.0)"
_API = "https://discord.com/api/v10"

_cached_channel_id: str | None = None


def _resolve_channel_id() -> str:
    """Pick the channel to read from.

    Priority:
      1. DISCORD_CHANNEL_ID, if explicitly set in .env
      2. The channel the DISCORD_WEBHOOK_URL targets (looked up once, cached)
    """
    global _cached_channel_id
    if _cached_channel_id is not None:
        return _cached_channel_id

    explicit = os.environ.get("DISCORD_CHANNEL_ID")
    if explicit:
        _cached_channel_id = explicit.strip()
        return _cached_channel_id

    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise RuntimeError(
            "No Discord channel configured — set DISCORD_CHANNEL_ID in .env "
            "or configure DISCORD_WEBHOOK_URL so we can derive it."
        )
    # Fetch webhook metadata to discover its channel_id
    req = urllib.request.Request(webhook, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    _cached_channel_id = data["channel_id"]
    return _cached_channel_id


def read_discord_messages(limit: int = 10) -> str:
    """Read the most recent messages from the Discord channel.

    Use this to check what people have been saying, see replies to something
    the assistant posted, or catch up on recent activity.

    Args:
        limit: How many recent messages to fetch (1–100, default 10).

    Returns:
        Messages as "author: content" lines, oldest first, or an error.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return "Discord bot is not configured — set DISCORD_BOT_TOKEN in .env."

    try:
        channel_id = _resolve_channel_id()
    except Exception as e:
        return f"Failed to resolve channel: {e}"

    n = max(1, min(100, int(limit)))
    url = f"{_API}/channels/{channel_id}/messages?limit={n}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": _UA,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            messages = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Discord rejected the bot token (401).  Check DISCORD_BOT_TOKEN."
        if e.code == 403:
            return ("Bot can't read this channel (403).  Invite the bot to the "
                    "server with 'View Channel' and 'Read Message History' "
                    "permissions.")
        if e.code == 404:
            return "Channel not found (404) — bot may not be in that server."
        body = e.read().decode(errors="replace") if hasattr(e, "read") else ""
        return f"Failed to read messages: HTTP {e.code} {body[:200]}"
    except Exception as e:
        return f"Failed to read messages: {e}"

    if not messages:
        return "No messages in the channel."

    # Discord returns newest-first; reverse for natural reading order
    lines = []
    for m in reversed(messages):
        author = m.get("author", {}).get("username", "unknown")
        content = (m.get("content") or "").strip() or "(no text)"
        lines.append(f"{author}: {content}")
    return "\n".join(lines)
