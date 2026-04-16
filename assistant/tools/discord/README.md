# Discord Tool

Enables the assistant to post messages to a Discord channel via an **incoming
webhook** — no bot account, no OAuth, no extra dependencies.

Once set up, you can say things like:
- *"Post a good-morning message in our team channel"*
- *"Tell the channel I'm done for the day"*

The tool is **auto-registered**: the LLM only sees it when
`DISCORD_WEBHOOK_URL` is present in your environment.  Leave it unset and the
assistant simply won't have Discord capability.

---

## Setup (one-time, ~1 minute)

### 1. Create a webhook in Discord

1. Open Discord and go to the channel you want to post into.
2. Click the **gear icon** next to the channel name (channel settings).
3. **Integrations → Webhooks → New Webhook**.
4. Give it a name (e.g. "Voice Assistant") and optionally an avatar.
5. Click **Copy Webhook URL**.

> You need *Manage Webhooks* permission on the channel.  On a server you don't
> own, ask the admin to create it for you and share the URL.

### 2. Add the URL to your `.env`

```bash
echo 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXX/YYYY' >> .env
```

That's it.  Restart the assistant and the tool becomes available.

---

## Capabilities and limitations

| Can                          | Can't                              |
|------------------------------|------------------------------------|
| Post messages (text, emoji)  | Read messages from the channel     |
| Up to 2000 chars per message | Post to a different channel        |
| Use the custom name/avatar   | DM users                           |
|                              | React to or edit existing messages |

If you need any of the right-column features, upgrade to a Discord **bot
token**: create an app at <https://discord.com/developers/applications>, add a
bot, invite it with the right scopes, and extend `client.py` to use
`discord.py` or raw `POST /channels/{id}/messages` calls.

---

## Security notes

- The webhook URL is effectively a write-only posting key for that one
  channel.  If leaked, someone can spam the channel but **cannot read it** or
  access any other part of your Discord account.
- Store the URL in `.env` (which is gitignored), never commit it.
- Delete the webhook from Discord's UI to revoke access instantly.

---

## Troubleshooting

**Tool not appearing to the LLM** — confirm the env var is loaded:
```bash
uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(bool(os.environ.get('DISCORD_WEBHOOK_URL')))"
```
Should print `True`.

**`Failed to post to Discord: HTTP Error 401`** — webhook URL is invalid or
deleted.  Create a new one.

**`HTTP Error 429`** — Discord rate limit (30 requests / minute per webhook).
Wait a moment and retry.
