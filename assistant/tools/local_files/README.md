# Local File Manager Tool

A four-function local file manager over one sandboxed folder.  Lets the
assistant browse, read, write, and search the notes/drafts you keep on
disk.

| Tool | Purpose |
|---|---|
| `list_directory` | See what's in a folder |
| `read_file`      | Read the text of a file |
| `write_file`     | Create a file, or append/overwrite an existing one |
| `search_files`   | Find a file by name (case-insensitive substring, recursive) |

All four share one env var and one sandboxed root.

| Env var | Setup | Purpose |
|---|---|---|
| `LOCAL_FILES_DIR` | ~10 s | Root folder the tools can operate inside |

Example voice prompts:
- *"What's in my notes folder?"* → `list_directory`
- *"Read my todo list"* → `search_files("todo")` then `read_file(...)`
- *"Save to shopping.txt: milk, eggs"* → `write_file` (appends)
- *"Find my notes about Discord"* → `search_files("discord")`
- *"Start over on shopping.txt with just bread"* → `write_file(..., append=False)`

---

## Setup

Pick a folder dedicated to the assistant — NOT your home directory or a
project you care about.

```bash
mkdir -p ~/Documents/assistant-notes
echo 'LOCAL_FILES_DIR=~/Documents/assistant-notes' >> .env
```

Restart the assistant and the four tools become available.

If you already sync a folder via iCloud / Dropbox / Obsidian, point
`LOCAL_FILES_DIR` at a sub-folder there and everything you save
syncs to your other devices for free.

---

## Safety

- **Sandboxed to one root.** Every path is resolved and checked to still
  live under `LOCAL_FILES_DIR`.  Rejects `..` traversal, absolute paths,
  and symlinks that try to escape.
- **Sub-folders allowed.** The LLM can organise into `journal/2026-04-17.md`
  etc. — parent directories are created on demand.
- **Append by default.** `write_file` adds to the end of an existing
  file unless you explicitly tell the LLM to overwrite.  One casual
  "save this" won't wipe a file.
- **No delete, move, or execute.** The four tools here are the whole
  surface.  The LLM cannot remove files, rename them, or run commands
  against the folder.
- **Read is UTF-8 text only, capped at 8 KB.** Binary files get refused
  with a clear message instead of being fed in as mojibake.  Oversize
  text files are truncated with an explicit marker so nothing is
  silently dropped.
- **Hidden files are hidden.** Entries starting with `.` (like
  `.DS_Store`) don't show up in listings or search results.

---

## Troubleshooting

**Tools not appearing to the LLM** — confirm the env var is loaded:
```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from assistant.tools import TOOLS
print([t.__name__ for t in TOOLS])"
```

**"Local files not configured"** — `LOCAL_FILES_DIR` is unset or empty.

**"Refused: ... resolves outside the configured folder"** — the LLM
tried a path that escaped the sandbox (`..`, absolute path, or a
symlink pointing out).  Ask again with a plain relative filename.

**"Not UTF-8 text — refusing to return binary content"** — the file
is binary (image, PDF, etc.).  This tool only handles text; use the
appropriate app to open binaries.

**"Failed to write ... PermissionError"** — the folder isn't writable
by your user, or is on a read-only volume.  Check with
`ls -ld "$LOCAL_FILES_DIR"`.
