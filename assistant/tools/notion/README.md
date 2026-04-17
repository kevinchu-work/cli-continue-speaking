# Notion Tool

Append notes to one Notion page, and read them back.

| Tool | Env vars | Setup | Purpose |
|---|---|---|---|
| `append_to_notion` | `NOTION_TOKEN`, `NOTION_PAGE_ID` | ~3 min | Add text to one pinned page |
| `read_notion_page` | same | — | Read back the page's current content |

Example voice prompts:
- *"Save to Notion: don't forget to renew the domain in May"* → append
- *"What's in my Notion notes?"* → read
- *"Add a paragraph to my Notion: today I finally fixed the 403 bug"* → append

The tool is deliberately scoped to **one page** — simple, predictable,
and the LLM can't wander into other parts of your workspace.

---

## Setup — three steps

### 1. Create an integration

1. Open <https://www.notion.so/my-integrations>
2. **New integration** → give it a name (e.g. "Voice Assistant") → pick
   the workspace → **Save**
3. Under **Capabilities** leave the defaults (read + update content).
4. Copy the **Internal Integration Secret** — starts with `ntn_` or `secret_`.

### 2. Share one page with the integration

Integrations can't see anything by default — you have to hand them a
page explicitly.

1. Open (or create) the Notion page you want to use as the assistant's
   notebook.  A blank page called *"Voice Notes"* is a fine start.
2. Click the **⋯** menu (top right) → **Connections** → *Add connections*
   → pick your integration.
3. Confirm.  The integration now has read/write on this page and any of
   its sub-pages.

### 3. Put both values in `.env`

You need the **page ID** from the URL.  A Notion page URL looks like:

```
https://www.notion.so/Voice-Notes-1a2b3c4d5e6f7890abcdef1234567890
                                    └──────────── page ID ─────────┘
```

The 32-char hex chunk at the end is the ID.  You can paste it with or
without dashes; the client normalises it.

```bash
echo 'NOTION_TOKEN=ntn_XXXXXXXXXXXXXXXXXXXXXXXXX' >> .env
echo 'NOTION_PAGE_ID=1a2b3c4d5e6f7890abcdef1234567890' >> .env
```

Restart the assistant and both tools are available.

---

## Capabilities

| Can | Can't |
|---|---|
| Append paragraphs to one page | Write to any other page |
| Split multi-paragraph content into separate blocks | Create sub-pages |
| Read back page text (paragraphs, headings, lists, to-dos, quotes) | Modify or delete existing blocks |
| Handle content longer than Notion's 2000-char block limit via chunking | Read images, databases, or embeds (they render as `[type]`) |
| Follow pagination when reading long pages | Search the workspace |

If you later want multi-page support, sub-page creation, or database
rows, those are all feasible extensions — holler.

---

## Security notes

- **Integration token** = read/write access to every page you've shared
  with it.  Treat it like a password; put it in `.env` (gitignored).
- **Only the one shared page is reachable.**  Sharing more pages is an
  explicit action you take in Notion's UI — the assistant can't escalate.
- To revoke: delete the integration at
  <https://www.notion.so/my-integrations>.  Takes effect instantly.

---

## Troubleshooting

**Tool not appearing to the LLM** — both env vars must be set:
```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from assistant.tools import TOOLS
print([t.__name__ for t in TOOLS])"
```

**`Notion API 401`** — token is wrong or was rotated.  Copy it again
from the integration page.

**`Notion API 404: Could not find block`** — the integration hasn't
been added to the page.  Re-do step 2 of setup: page menu → Connections
→ add your integration.

**`NOTION_PAGE_ID looks wrong`** — you copied something that isn't a
page ID.  It must be 32 hex characters (or 36 with dashes); you'll find
it as the last path segment of the Notion URL.

**Content coming through garbled / partial** — probably went past the
2000-char per-block limit and the chunking split it oddly.  The tool
will still save everything, just in more blocks than you'd expect.
