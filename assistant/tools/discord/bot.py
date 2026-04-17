"""Discord bot client — read channel messages via the REST API.

Unlike webhooks (write-only, single channel, no identity), a bot token gives
the assistant a real Discord identity with channel-read permissions.

Voice messages (Discord's hold-to-record feature) are auto-transcribed using
the same mlx-whisper model the mic pipeline uses — transcriptions are cached
by message ID so re-reads are free.
"""

import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_UA = "DiscordBot (https://github.com/kevin/v-to-work, 0.1.0)"
_API = "https://discord.com/api/v10"

# Discord message flag bits (https://discord.com/developers/docs/resources/message)
_FLAG_IS_VOICE_MESSAGE = 1 << 13   # 8192

_cached_channel_id: str | None = None
_transcription_cache: dict[str, str] = {}


def _transcribe_voice_attachment(msg: dict) -> str | None:
    """Return the Whisper transcription if msg is a voice message, else None.

    Downloads the .ogg attachment to a temp file, runs mlx-whisper on it, and
    caches the result by message ID so subsequent reads of the same message
    don't re-transcribe.  Errors are returned as a parenthesised string rather
    than raised, so one bad attachment doesn't sink the whole read.
    """
    if not (msg.get("flags", 0) & _FLAG_IS_VOICE_MESSAGE):
        return None

    msg_id = msg["id"]
    if msg_id in _transcription_cache:
        return _transcription_cache[msg_id]

    attachments = msg.get("attachments") or []
    if not attachments or not attachments[0].get("url"):
        return "(voice message with no attachment)"

    audio_url = attachments[0]["url"]
    tmp_path: str | None = None
    try:
        # Discord's CDN sits behind Cloudflare and 403s the default
        # python-urllib UA (same 1010 block as the webhook endpoint).
        audio_req = urllib.request.Request(audio_url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(audio_req, timeout=15) as resp:
            audio_bytes = resp.read()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
            tf.write(audio_bytes)
            tmp_path = tf.name

        # Imported lazily — mlx-whisper is already loaded by the main app, so
        # this is just a dict lookup and the model is warm.
        import mlx_whisper
        from assistant.config import WHISPER_MODEL

        result = mlx_whisper.transcribe(tmp_path, path_or_hf_repo=WHISPER_MODEL)
        text = (result.get("text") or "").strip() or "(empty)"
    except Exception as e:
        # Prefixed with ERROR so the LLM can't miss it and smooth it over.
        text = f"ERROR transcribing voice message: {type(e).__name__}: {e}"
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    # Only cache successful transcriptions — errors are usually transient
    # (network, auth, CDN signature expiry) and should be retried next read.
    if not text.startswith("ERROR"):
        _transcription_cache[msg_id] = text
    return text


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


def fetch_raw_messages(limit: int = 10, after: str | None = None) -> list[dict]:
    """Fetch raw Discord message dicts — newest first from the API.

    Used by both ``read_discord_messages`` (LLM tool) and the auto-reply
    poller.  Raises on any error — callers decide how to surface it.

    Args:
        limit: 1–100.
        after: Discord snowflake ID; only return messages strictly newer
            than this.  Used by the poller to get just what arrived since
            the last tick.
    """
    token = os.environ["DISCORD_BOT_TOKEN"]
    channel_id = _resolve_channel_id()
    n = max(1, min(100, int(limit)))
    url = f"{_API}/channels/{channel_id}/messages?limit={n}"
    if after:
        url += f"&after={after}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bot {token}", "User-Agent": _UA},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def format_message(msg: dict) -> str:
    """Render one raw message as the human-readable line the LLM sees."""
    author = msg.get("author", {}).get("username", "unknown")
    voice_text = _transcribe_voice_attachment(msg)
    if voice_text is not None:
        return f"{author} [voice]: {voice_text}"
    content = (msg.get("content") or "").strip() or "(no text)"
    return f"{author}: {content}"


def read_discord_messages(limit: int = 10) -> str:
    """Read the most recent messages from the Discord channel.

    Use this to check what people have been saying, see replies to something
    the assistant posted, or catch up on recent activity.

    Args:
        limit: How many recent messages to fetch (1–100, default 10).

    Returns:
        Messages as "author: content" lines, oldest first, or an error.
    """
    if not os.environ.get("DISCORD_BOT_TOKEN"):
        return "Discord bot is not configured — set DISCORD_BOT_TOKEN in .env."

    try:
        messages = fetch_raw_messages(limit=limit)
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
    return "\n".join(format_message(m) for m in reversed(messages))
