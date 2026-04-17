"""Notion client — append paragraphs to one page, read its text back.

Deliberately scoped to ONE page (configured via NOTION_PAGE_ID) rather
than letting the LLM roam the workspace.  One page = one journal-ish
target.  If the user wants multiple destinations later we can add a
``page_id`` argument — but the default should stay sandboxed.

Notion-specific quirks handled here:
    * Rich-text content has a 2000-char limit per block.  We split longer
      content on paragraph boundaries, falling back to hard-chunking
      mid-text if any single paragraph exceeds the limit.
    * The "page ID" in Notion URLs is a 32-char hex string with no
      dashes; the API wants it formatted as a UUID (8-4-4-4-12).  We
      normalise on the way in so users can paste either form.
    * Block listing is paginated — we follow ``next_cursor`` until done.
"""

import json
import os
import urllib.error
import urllib.request

_API = "https://api.notion.com/v1"
_VERSION = "2022-06-28"
_RICH_TEXT_LIMIT = 2000   # Notion hard-cap per rich_text chunk


def _page_id() -> str:
    """Return the configured page ID in 8-4-4-4-12 UUID form."""
    raw = os.environ["NOTION_PAGE_ID"].strip().replace("-", "")
    if len(raw) != 32:
        raise RuntimeError(
            f"NOTION_PAGE_ID looks wrong — expected 32 hex chars "
            f"(with or without dashes), got {len(raw)}."
        )
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": _VERSION,
        "Content-Type": "application/json",
        "User-Agent": "v-to-work-assistant/0.1.0",
    }


def _http(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # Include Notion's JSON error message — it's actually helpful,
        # unlike HTTP status alone (e.g. "object_not_found: ensure the
        # integration is shared with this page").
        try:
            payload = json.loads(e.read().decode(errors="replace"))
            msg = payload.get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"Notion API {e.code}: {msg or e.reason}") from e


# ── Public tool functions ────────────────────────────────────────────────────


def append_to_notion(content: str) -> str:
    """Append text to the configured Notion page.

    Use this to save notes, quotes, ideas, journal entries, or anything
    the user asks you to "add to Notion" / "save to my Notion" /
    "write down in Notion".

    Content with blank-line-separated paragraphs becomes multiple
    paragraph blocks in Notion; single-line content becomes one block.

    Args:
        content: Text to append.  Any length — long content is split on
            paragraph boundaries (or hard-chunked) to stay under Notion's
            per-block 2000-char limit.

    Returns:
        Confirmation with block count, or an error.
    """
    if not content or not content.strip():
        return "Refused: empty content."

    try:
        pid = _page_id()
    except Exception as e:
        return f"Notion not configured correctly: {e}"

    blocks = _content_to_blocks(content)
    try:
        _http("PATCH", f"{_API}/blocks/{pid}/children", {"children": blocks})
    except Exception as e:
        return f"Failed to append to Notion: {e}"

    return f"Appended {len(blocks)} block(s) to Notion."


def create_notion_subpage(title: str, content: str = "") -> str:
    """Create a new sub-page under the configured Notion page.

    Use this when the user asks to "start a new note" / "make a new
    page" / "create a Notion page for X" — anything that should be its
    own titled entry rather than appended to the existing journal.

    Args:
        title: Page title.  Required, non-empty.
        content: Optional initial body text.  Same splitting rules as
            ``append_to_notion`` — blank-line-separated paragraphs
            become separate blocks, and over-long paragraphs are
            chunked under Notion's 2000-char limit.

    Returns:
        Confirmation with the new page's URL, or an error.
    """
    title = (title or "").strip()
    if not title:
        return "Refused: page needs a non-empty title."

    try:
        parent_id = _page_id()
    except Exception as e:
        return f"Notion not configured correctly: {e}"

    body: dict = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            # Sub-pages under a page (not a database) use "title" — a
            # rich-text array.  Databases would use a named property.
            "title": {
                "title": [{"type": "text", "text": {"content": title}}],
            },
        },
    }
    if content and content.strip():
        body["children"] = _content_to_blocks(content)

    try:
        resp = _http("POST", f"{_API}/pages", body)
    except Exception as e:
        return f"Failed to create Notion sub-page: {e}"

    url = resp.get("url", "(no url returned)")
    return f"Created '{title}' → {url}"


def read_notion_page() -> str:
    """Read the text content of the configured Notion page.

    Use this when the user asks what's in their Notion notes, to recall
    something saved earlier, or before appending so you don't duplicate.

    Returns:
        Plain-text concatenation of paragraph/heading/list blocks on the
        page, or an error.  Non-text blocks (embeds, databases, images)
        are represented by a short ``[type]`` placeholder.
    """
    try:
        pid = _page_id()
    except Exception as e:
        return f"Notion not configured correctly: {e}"

    lines: list[str] = []
    cursor: str | None = None
    try:
        while True:
            url = f"{_API}/blocks/{pid}/children?page_size=100"
            if cursor:
                url += f"&start_cursor={cursor}"
            resp = _http("GET", url)
            for block in resp.get("results", []):
                lines.append(_render_block(block))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
    except Exception as e:
        return f"Failed to read Notion page: {e}"

    text = "\n".join(line for line in lines if line).strip()
    return text or "(page is empty)"


# ── Internals ────────────────────────────────────────────────────────────────


def _content_to_blocks(content: str) -> list[dict]:
    """Split text into Notion paragraph blocks, respecting the char limit."""
    blocks: list[dict] = []
    # Treat blank lines as paragraph separators — matches how humans
    # usually format multi-paragraph notes.
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [content.strip()]

    for para in paragraphs:
        # Hard-chunk any paragraph that exceeds the rich-text limit so
        # we never silently truncate.
        for i in range(0, len(para), _RICH_TEXT_LIMIT):
            chunk = para[i : i + _RICH_TEXT_LIMIT]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": chunk}}
                    ],
                },
            })
    return blocks


def _render_block(block: dict) -> str:
    """Turn one Notion block into a plain-text line (best-effort)."""
    btype = block.get("type", "")
    body = block.get(btype, {}) if btype else {}
    rich = body.get("rich_text")
    if isinstance(rich, list):
        text = "".join(rt.get("plain_text", "") for rt in rich)
        # Prefix headings / list items so structure is readable aloud.
        if btype == "heading_1":
            return f"# {text}"
        if btype == "heading_2":
            return f"## {text}"
        if btype == "heading_3":
            return f"### {text}"
        if btype == "bulleted_list_item":
            return f"- {text}"
        if btype == "numbered_list_item":
            return f"1. {text}"
        if btype == "to_do":
            checked = body.get("checked", False)
            return f"[{'x' if checked else ' '}] {text}"
        if btype == "quote":
            return f"> {text}"
        return text
    # Non-text blocks — give the LLM enough to describe but not garbage.
    return f"[{btype}]" if btype else ""
