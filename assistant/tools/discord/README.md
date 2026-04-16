# Discord Tool

Two independent capabilities, each controlled by its own env var:

| Tool | Env var | Setup | Purpose |
|---|---|---|---|
| `send_discord_message` | `DISCORD_WEBHOOK_URL` | ~1 min | Post into a single channel |
| `read_discord_messages` | `DISCORD_BOT_TOKEN` | ~5 min | Read recent channel history |

You can enable one, both, or neither — each tool auto-registers only when
its setup is present.

Example voice prompts:
- *"Post good-morning in our team channel"* → `send_discord_message`
- *"What did people say on Discord?"* → `read_discord_messages`

---

## Setup — write (webhook)

### 1. Create a webhook in Discord

1. Open Discord and go to the channel you want to post into.
2. Click the **gear icon** next to the channel name (channel settings).
3. **Integrations → Webhooks → New Webhook**.
4. Give it a name (e.g. "Voice Assistant") and optionally an avatar.
5. Click **Copy Webhook URL**.

> You need *Manage Webhooks* permission on the channel.  On a server you
> don't own, ask the admin to create it for you and share the URL.

### 2. Add the URL to `.env`

```bash
echo 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXX/YYYY' >> .env
```

Restart the assistant and `send_discord_message` becomes available.

---

## Setup — read (bot token)

### 1. Create a Discord application + bot

1. Open <https://discord.com/developers/applications> → **New Application**.
2. Give it a name (e.g. "Voice Assistant") → Create.
3. Left sidebar → **Bot** → **Reset Token** → copy the token.
4. On the same **Bot** page, scroll to **Privileged Gateway Intents**:
   - Toggle **Message Content Intent** ON.  *Without this, Discord returns
     empty `content` for every message the bot didn't author.*
   - Save Changes.

### 2. Invite the bot to your server

1. Left sidebar → **OAuth2 → URL Generator**.
2. Scopes: check **`bot`**.
3. Bot Permissions: check **View Channel** and **Read Message History**.
4. Copy the generated URL, open it in a browser, pick the server, Authorize.

### 3. Add the token to `.env`

```bash
echo 'DISCORD_BOT_TOKEN=MTxxxxxxxxxxxxxxxxxxxx.Gxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' >> .env
```

The channel to read from is picked as:
1. `DISCORD_CHANNEL_ID` if explicitly set, else
2. The channel the webhook URL posts to (derived automatically).

Most people only need the webhook set — no need to add `DISCORD_CHANNEL_ID`.

---

## Capabilities

| Can | Can't |
|---|---|
| Post messages (webhook) | Post as a real user (only the bot/webhook identity) |
| Read recent messages (bot) | Send DMs |
| Read message authors + timestamps | React to or edit existing messages |
| Up to 2000 chars per message | Read channels the bot isn't in |

For reactions, edits, or DMs, extend `bot.py` with more REST endpoints.
For real-time events (live message notifications), you'd need a Discord
gateway connection (use `discord.py` library).

---

## Security notes

- **Webhook URL** — write-only posting key for one channel.  If leaked,
  someone can spam the channel but cannot read it or access anything else.
  Delete it from Discord's UI to revoke instantly.
- **Bot token** — grants read access to every channel the bot is in.
  Treat it like a password.  Reset it in the Developer Portal to revoke.
- Both go in `.env` (gitignored), never commit.

---

## Troubleshooting

**Tool not appearing to the LLM** — confirm env vars are loaded:
```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from assistant.tools import TOOLS
print([t.__name__ for t in TOOLS])"
```

**Every message shows `(no text)`** — **Message Content Intent** isn't
enabled on the bot (Developer Portal → Bot → Privileged Gateway Intents).
This is a 2022 Discord privacy feature; without it, `content` is blanked
for every message the bot didn't author or wasn't @-mentioned in.

**`Discord rejected the bot token (401)`** — token invalid or reset in
the Developer Portal.  Generate a new one.

**`Bot can't read this channel (403)`** — bot was invited but lacks
`View Channel` / `Read Message History` permissions on that channel.
Either re-invite with the correct scopes via the OAuth2 URL Generator or
adjust the bot's role permissions in the server's settings.

**`Channel not found (404)`** — the bot isn't a member of that server,
or `DISCORD_CHANNEL_ID` points to a channel the bot can't see.

**`Failed to post to Discord: HTTP Error 401`** — webhook URL is invalid
or deleted.  Create a new one.

**`HTTP Error 403` with "error code: 1010"** — Cloudflare blocked the
request because the User-Agent is missing or on a blocklist.  Discord
requires a UA in the form `DiscordBot (URL, Version)`; the client sets
this automatically, so if you hit 1010 it usually means you're running
an outdated copy of `client.py`.

**`HTTP Error 429`** — Discord rate limit.  Wait a moment and retry.
