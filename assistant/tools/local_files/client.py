"""Local file-manager tools — four functions over one sandboxed folder.

All paths the LLM hands us go through ``_safe_path`` which resolves,
defends against ``..`` / absolute-path traversal, and keeps the target
inside ``LOCAL_FILES_DIR``.  The LLM can organise into sub-folders;
it cannot escape.

Tool surface:
    list_directory(path="")           — list immediate children
    read_file(path)                   — read a text file (UTF-8, capped)
    write_file(path, content, append) — create or update a text file
    search_files(query)               — recursive filename search
"""

import os
from pathlib import Path

# Cap read output so a huge file doesn't blow the LLM's context window
# or the TTS buffer.  8 KB is ~1500 words — plenty for notes/journals.
_READ_MAX_BYTES = 8 * 1024

# Cap directory listings + search hits — a huge folder shouldn't stall
# the LLM context.  The listing includes an explicit truncation note.
_LIST_MAX_ENTRIES = 200
_SEARCH_MAX_HITS = 100


# ── Internals ────────────────────────────────────────────────────────────────


def _root() -> Path:
    """Resolved absolute root.  Raises if LOCAL_FILES_DIR is unset."""
    raw = os.environ.get("LOCAL_FILES_DIR")
    if not raw:
        raise RuntimeError(
            "LOCAL_FILES_DIR is not set — cannot access local files."
        )
    # expanduser handles "~/Documents/notes" gracefully
    return Path(raw).expanduser().resolve()


def _safe_path(user_path: str) -> tuple[Path | None, str | None]:
    """Resolve ``user_path`` inside the sandbox.

    Returns ``(resolved_path, None)`` on success, or ``(None, error_msg)``
    if the path is invalid or escapes the sandbox.  The resolved path
    may or may not exist — that's a tool-level concern.
    """
    try:
        root = _root()
    except Exception as e:
        return None, f"Local files not configured: {e}"

    # Empty string / "." / "./" all mean "the root itself" — handy for
    # list_directory without arguments.
    cleaned = (user_path or "").strip()
    candidate = (root / cleaned).expanduser() if cleaned else root

    try:
        resolved = candidate.resolve()
    except OSError as e:
        return None, f"Invalid path: {e}"

    try:
        resolved.relative_to(root)
    except ValueError:
        return None, (
            f"Refused: '{user_path}' resolves outside the configured "
            f"folder ({root}).  Use a relative path without '..'."
        )
    return resolved, None


def _rel(path: Path) -> str:
    """Format a path as root-relative for user-facing output."""
    try:
        return str(path.relative_to(_root())) or "."
    except Exception:
        return str(path)


# ── Public tools ─────────────────────────────────────────────────────────────


def list_directory(path: str = "") -> str:
    """List the contents of a folder under the user's files root.

    Use this to see what files exist before reading or writing, or when
    the user asks "what's in my notes folder?" / "what files do I have
    about X?" / "show me the folder".

    Args:
        path: Relative folder path inside the root.  Empty string (the
            default) lists the root itself.  Sub-folders supported;
            absolute paths and ".." traversal rejected.

    Returns:
        Lines of ``<name>    <type>    <size/entries>``, directories
        first, hidden files (leading dot) hidden.  Or an error.
    """
    target, err = _safe_path(path)
    if err:
        return err
    if not target.exists():
        return f"Folder not found: {path or '(root)'}"
    if not target.is_dir():
        return f"Not a folder: {path}"

    try:
        entries = [e for e in target.iterdir() if not e.name.startswith(".")]
    except Exception as e:
        return f"Failed to list {path or '(root)'}: {type(e).__name__}: {e}"

    # Directories before files, alphabetical within each group — feels
    # natural when read aloud and matches `ls -p`.
    dirs  = sorted((e for e in entries if e.is_dir()),  key=lambda p: p.name.lower())
    files = sorted((e for e in entries if e.is_file()), key=lambda p: p.name.lower())
    ordered = dirs + files

    if not ordered:
        return f"{_rel(target)}/ is empty."

    truncated = len(ordered) > _LIST_MAX_ENTRIES
    ordered = ordered[:_LIST_MAX_ENTRIES]

    lines = [f"Contents of {_rel(target)}/:"]
    for e in ordered:
        if e.is_dir():
            try:
                count = sum(1 for _ in e.iterdir())
            except Exception:
                count = "?"
            lines.append(f"  {e.name}/   dir    {count} entries")
        else:
            try:
                size = e.stat().st_size
            except Exception:
                size = 0
            lines.append(f"  {e.name}    file   {size} bytes")

    if truncated:
        lines.append(f"  ...[truncated — folder has more than {_LIST_MAX_ENTRIES} entries]")
    return "\n".join(lines)


def read_file(path: str) -> str:
    """Read the UTF-8 text content of a file under the user's files root.

    Use this when the user asks what's in a file, to check before
    appending, or to summarise / recall something previously saved.

    Args:
        path: Relative path inside the root.  Sub-folders supported;
            absolute paths and ".." traversal rejected.

    Returns:
        The file's text, or an error.  Large files are truncated with
        an explicit ``...[truncated]`` marker so nothing is silently
        dropped.  Binary files are refused rather than garbled.
    """
    target, err = _safe_path(path)
    if err:
        return err
    if not target.exists():
        return f"File not found: {path}"
    if not target.is_file():
        return f"Not a regular file: {path}"

    try:
        data = target.read_bytes()
    except Exception as e:
        return f"Failed to read {path}: {type(e).__name__}: {e}"

    total = len(data)
    truncated = total > _READ_MAX_BYTES
    if truncated:
        data = data[:_READ_MAX_BYTES]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return (
            f"{path} is not UTF-8 text ({total} bytes) — refusing to "
            f"return binary content."
        )

    if truncated:
        text += f"\n...[truncated — file is {total} bytes, showing first {_READ_MAX_BYTES}]"
    return text


def write_file(path: str, content: str, append: bool = True) -> str:
    """Create or update a text file under the user's files root.

    Use this to save notes, drafts, transcripts, or anything the user
    asks you to "save" / "write down" / "keep" / "add to ...".

    Args:
        path: Relative path inside the root.  Sub-folders are allowed
            (e.g. "journal/2026-04-17.md") and created as needed.
            Absolute paths and ".." traversal are rejected.
        content: The text to write.
        append: Default TRUE — add to the end of the file (with a
            newline separator if needed).  Set to False ONLY when the
            user explicitly asks to "overwrite" / "replace" / "start
            over", since overwriting discards whatever was there.

    Returns:
        Confirmation with the final path and size, or an error.
    """
    target, err = _safe_path(path)
    if err:
        return err

    # Don't let the LLM accidentally "write" to a directory — silent
    # FileNotFoundError would be confusing; be explicit.
    if target.exists() and target.is_dir():
        return f"Refused: '{path}' is a folder, not a file."

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        # Insert a separating newline in append mode when the file
        # exists and doesn't already end in one — keeps notes readable.
        prefix = ""
        if append and target.exists() and target.stat().st_size > 0:
            with target.open("rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    prefix = "\n"
        with target.open(mode, encoding="utf-8") as f:
            f.write(prefix + content)
    except Exception as e:
        return f"Failed to write {path}: {type(e).__name__}: {e}"

    size = target.stat().st_size
    action = "Appended to" if append else "Wrote"
    return f"{action} {_rel(target)} ({size} bytes)."


def search_files(query: str) -> str:
    """Find files by name (case-insensitive substring match) recursively.

    Use this when the user asks "do I have a file about X?" / "find my
    notes on X" / "where did I save X?".  Returns matching paths
    relative to the root so ``read_file`` can be called directly.

    Args:
        query: Substring to look for in filenames.  Case-insensitive.
            Empty or whitespace-only queries are rejected (would match
            everything).

    Returns:
        Newline-separated relative paths, or a "no matches" note.
    """
    q = (query or "").strip().lower()
    if not q:
        return "Refused: search query is empty."

    try:
        root = _root()
    except Exception as e:
        return f"Local files not configured: {e}"

    hits: list[Path] = []
    try:
        # rglob over files only; skip dotfiles / dot-dirs to mirror the
        # list_directory hiding rule and avoid noise from .DS_Store etc.
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part.startswith(".") for part in p.relative_to(root).parts):
                continue
            if q in p.name.lower():
                hits.append(p)
                if len(hits) >= _SEARCH_MAX_HITS + 1:
                    break
    except Exception as e:
        return f"Search failed: {type(e).__name__}: {e}"

    if not hits:
        return f"No files matching '{query}'."

    truncated = len(hits) > _SEARCH_MAX_HITS
    hits = hits[:_SEARCH_MAX_HITS]

    lines = [f"Files matching '{query}':"]
    for p in sorted(hits, key=lambda x: str(x).lower()):
        lines.append(f"  {p.relative_to(root)}")
    if truncated:
        lines.append(f"  ...[truncated — more than {_SEARCH_MAX_HITS} matches]")
    return "\n".join(lines)
