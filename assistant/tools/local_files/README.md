# Local Files Tool

Lets the assistant save text to files on your disk — notes, transcripts,
drafts, journal entries, anything you ask it to "write down" or "save".

| Tool | Env var | Setup | Purpose |
|---|---|---|---|
| `write_local_file` | `LOCAL_FILES_DIR` | ~10 s | Append (default) or overwrite text in one folder |
| `read_local_file`  | `LOCAL_FILES_DIR` | —      | Read back a previously saved file |

Example voice prompts:
- *"Save a note that I need to call the plumber tomorrow"*
- *"Write a haiku about coffee and save it as haiku.txt"*
- *"What's in my todo list?"* → `read_local_file`
- *"Start over on shopping.txt with just milk and bread"* → overwrite

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
- **Appends by default.** Writes add to the end of the file; overwrite
  only happens when the LLM explicitly sets `append=False` in response
  to a user instruction like "start over" / "replace" / "overwrite".
  This is deliberately conservative — one phrase like "save this" is
  extremely unlikely to wipe a file.
- **No delete, list, or execute.** Read and write are separate tools;
  there's no way for the LLM to remove files, enumerate the folder,
  or run commands against it.
- **Read is UTF-8 text only, capped at 8 KB.** Binary files get refused
  rather than fed into the LLM as garbled mojibake, and big files are
  truncated with an explicit marker so nothing is silently dropped.

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
