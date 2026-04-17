"""Auto-reply service — polls Discord, drafts replies with the LLM, posts them.

Runs on a background daemon thread alongside the voice loop.  Opt-in via the
``auto_reply_enabled`` setting (toggled at runtime with Ctrl+R) and gated on
both ``DISCORD_BOT_TOKEN`` (to read) and ``DISCORD_WEBHOOK_URL`` (to post).

Design notes:
    * Polls every POLL_SECS via the REST API — simpler than a gateway
      connection and fine at human-timescale cadence.  Uses Discord's
      ``?after=<id>`` so each tick returns only genuinely new messages.
    * On first start we snapshot the current latest message ID and skip
      backlog.  The user shouldn't wake up to 30 auto-replies from
      yesterday.
    * The webhook identity posts with a distinct username — we filter
      those out so the bot doesn't react to its own replies and create
      an infinite loop.
    * Drafts go through ``LLMClient.draft_reply`` which uses a one-shot
      generate (not the voice chat session) so auto-reply context stays
      separate from the conversation the user is having out loud.
    * Holds off while the user is mid-turn (``busy_fn()`` returns True)
      so the terminal doesn't spew mid-sentence.
"""

import os
import threading
import time
import traceback
from typing import Callable

from .llm import LLMClient
from .tools.discord import bot as discord_bot
from .tools.discord.client import send_discord_message

POLL_SECS = 15


class AutoReplyService:
    def __init__(self, llm: LLMClient, busy_fn: Callable[[], bool]) -> None:
        self._llm = llm
        self._busy_fn = busy_fn
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_seen_id: str | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @staticmethod
    def available() -> bool:
        """True if the env is set up for both reading and posting."""
        return bool(
            os.environ.get("DISCORD_BOT_TOKEN")
            and os.environ.get("DISCORD_WEBHOOK_URL")
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="auto-reply", daemon=True)
        self._thread.start()
        print("[auto-reply] started — polling Discord every "
              f"{POLL_SECS}s, drafts posted automatically.")

    def stop(self) -> None:
        self._stop.set()
        # Don't join — daemon thread dies with the process; waiting would
        # stall Ctrl+C by up to POLL_SECS.
        print("[auto-reply] stopped.")

    # ── Internals ─────────────────────────────────────────────────────────────

    def _snapshot_latest_id(self) -> None:
        """Record the current newest message ID so we skip backlog."""
        try:
            msgs = discord_bot.fetch_raw_messages(limit=1)
            if msgs:
                self._last_seen_id = msgs[0]["id"]
        except Exception as e:
            print(f"[auto-reply] couldn't snapshot channel ({e}); "
                  "starting from next new message.")

    def _is_own_message(self, msg: dict) -> bool:
        """Skip messages the assistant itself posted, to avoid loops.

        Webhook posts arrive with ``webhook_id`` set, which is the cleanest
        signal — no name matching, no brittleness if the user renames the
        webhook in Discord's UI.
        """
        return bool(msg.get("webhook_id"))

    def _run(self) -> None:
        self._snapshot_latest_id()

        while not self._stop.is_set():
            # Sleep first so we don't hammer the API on a tight error loop,
            # and so the initial snapshot has a moment to settle.
            if self._stop.wait(POLL_SECS):
                return
            if self._busy_fn():
                continue
            try:
                self._tick()
            except Exception as e:
                print(f"[auto-reply] tick error: {type(e).__name__}: {e}")
                traceback.print_exc()

    def _tick(self) -> None:
        msgs = discord_bot.fetch_raw_messages(
            limit=10, after=self._last_seen_id
        )
        if not msgs:
            return

        # API returns newest-first; process oldest-first so replies land
        # in conversational order and last_seen advances monotonically.
        for msg in reversed(msgs):
            if self._is_own_message(msg):
                self._last_seen_id = msg["id"]
                continue
            self._handle(msg)
            self._last_seen_id = msg["id"]

    def _handle(self, msg: dict) -> None:
        rendered = discord_bot.format_message(msg)
        print(f"\n[auto-reply] new message: {rendered}")

        try:
            reply = self._llm.draft_reply(rendered)
        except Exception as e:
            print(f"[auto-reply] draft failed: {type(e).__name__}: {e}")
            return
        if not reply:
            print("[auto-reply] model returned empty draft; skipping.")
            return

        print(f"[auto-reply] posting: {reply}")
        result = send_discord_message(reply)
        print(f"[auto-reply] {result}")
