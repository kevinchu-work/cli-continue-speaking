# Local Files Tool

Lets the assistant save text to files on your disk — notes, transcripts,
drafts, journal entries, anything you ask it to "write down" or "save".

| Tool | Env var | Setup | Purpose |
|---|---|---|---|
| `write_local_file` | `LOCAL_FILES_DIR` | ~10 s | Write/append text to files inside one folder |

Example voice prompts:
- *"Save a note that I need to call the plumber tomorrow"*
- *"Write a haiku about coffee and save it as haiku.txt"*
- *"Append 'meeting moved to 3pm' to today's journal"*

---

## Setup

Pick a folder you're comfortable having the assistant write into — usually
a dedicated notes/drafts folder, NOT your home directory or a project
you care about.

```bash
mkdir -p ~/Documents/assistant-notes
echo 'LOCAL_FILES_DIR=~/Documents/assistant-notes' >> .env
```

Restart the assistant and `write_local_file` becomes available.

---

## Safety

- **Sandboxed to one folder.** Every write is confirmed to resolve inside
  `LOCAL_FILES_DIR`.  Paths like `../../etc/hosts`, absolute paths, or
  symlinks that escape the folder are rejected.
- **Sub-folders allowed.** The LLM can organise into `journal/2026-04-17.md`
  etc. — parent directories are created as needed.
- **Overwrites by default.** The `append` flag exists for additive writes;
  without it the tool replaces the file's contents.  If that worries you,
  pick a folder with nothing important in it.
- **No read, delete, list, or execute.** This tool only writes.  The LLM
  cannot inspect what's already there, remove files, or run commands
  against the folder.  If you want read capability, we'd add a separate
  tool — keeps the surface area small and obvious.

---

## Troubleshooting

**Tool not appearing to the LLM** — check the env var is loaded:
```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from assistant.tools import TOOLS
print([t.__name__ for t in TOOLS])"
```

**"Local files not configured"** — `LOCAL_FILES_DIR` is unset or empty.

**"Refused: ... resolves outside the configured folder"** — the LLM tried
a path that escaped the sandbox (`..`, absolute, or a symlink pointing out).
Rephrase your request to use a plain relative filename.

**"Failed to write ... PermissionError"** — the folder isn't writable by
your user, or is on a read-only volume.  Check with `ls -ld "$LOCAL_FILES_DIR"`.
