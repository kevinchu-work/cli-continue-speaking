"""Write text content to files under a user-configured root folder.

The LLM can only write inside LOCAL_FILES_DIR — any path that resolves
outside it (via ``..`` or absolute paths) is rejected.  Sub-folders are
allowed and are created on demand, so the LLM can organise notes under
dated folders, project folders, etc.
"""

import os
from pathlib import Path


def _root() -> Path:
    """Resolved absolute root.  Raises if LOCAL_FILES_DIR is unset."""
    raw = os.environ.get("LOCAL_FILES_DIR")
    if not raw:
        raise RuntimeError(
            "LOCAL_FILES_DIR is not set — cannot write local files."
        )
    # expanduser handles "~/Documents/notes" gracefully
    return Path(raw).expanduser().resolve()


def write_local_file(
    filename: str,
    content: str,
    append: bool = True,
) -> str:
    """Save text content to a file in the user's configured notes folder.

    Use this to take notes, save drafts, dump transcripts, or persist
    anything the user asks you to "save" / "write down" / "keep".

    Args:
        filename: Relative path inside the notes folder.  Sub-folders are
            allowed (e.g. "journal/2026-04-17.md") and created as needed.
            Absolute paths and ".." traversal are rejected.
        content: The text to write.
        append: Default TRUE — add to the end of the file (with a newline
            separator if needed) rather than replacing.  Only set to False
            when the user explicitly asks to "overwrite" / "replace" /
            "start over" on the file, since overwriting permanently
            discards whatever was there.

    Returns:
        Confirmation with the final path and size, or an error.
    """
    try:
        root = _root()
    except Exception as e:
        return f"Local files not configured: {e}"

    # Normalise + defend against traversal.  We resolve() the *candidate*
    # full path and check it's still inside root — catches "../x", symlinks
    # that escape, absolute paths, and anything else ingenious.
    candidate = (root / filename).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError as e:
        return f"Invalid path: {e}"

    try:
        resolved.relative_to(root)
    except ValueError:
        return (
            f"Refused: '{filename}' resolves outside the configured "
            f"folder ({root}).  Use a relative path without '..'."
        )

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        # Add a separating newline in append mode if the file exists and
        # doesn't already end in one — keeps notes readable.
        prefix = ""
        if append and resolved.exists() and resolved.stat().st_size > 0:
            with resolved.open("rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    prefix = "\n"
        with resolved.open(mode, encoding="utf-8") as f:
            f.write(prefix + content)
    except Exception as e:
        return f"Failed to write {filename}: {type(e).__name__}: {e}"

    size = resolved.stat().st_size
    action = "Appended to" if append else "Wrote"
    return f"{action} {resolved} ({size} bytes)."


# Cap read output so a huge file doesn't blow the LLM's context window
# or the TTS buffer.  8 KB is ~1500 words — plenty for notes/journals.
_READ_MAX_BYTES = 8 * 1024


def read_local_file(filename: str) -> str:
    """Read back text content from a file in the user's notes folder.

    Use this when the user asks what's in a note, to check before
    appending, or to summarise/recall something previously saved.

    Args:
        filename: Relative path inside the notes folder (same rules as
            write_local_file — no absolute paths, no ".." traversal).

    Returns:
        The file's text, or an error message.  Large files are truncated
        with an explicit "...[truncated]" marker so you never silently
        return only part of a file.
    """
    try:
        root = _root()
    except Exception as e:
        return f"Local files not configured: {e}"

    candidate = (root / filename).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError as e:
        return f"Invalid path: {e}"

    try:
        resolved.relative_to(root)
    except ValueError:
        return (
            f"Refused: '{filename}' resolves outside the configured "
            f"folder ({root}).  Use a relative path without '..'."
        )

    if not resolved.exists():
        return f"File not found: {filename}"
    if not resolved.is_file():
        return f"Not a regular file: {filename}"

    try:
        data = resolved.read_bytes()
    except Exception as e:
        return f"Failed to read {filename}: {type(e).__name__}: {e}"

    total = len(data)
    truncated = total > _READ_MAX_BYTES
    if truncated:
        data = data[:_READ_MAX_BYTES]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return (
            f"{filename} is not UTF-8 text ({total} bytes) — refusing "
            f"to return binary content."
        )

    if truncated:
        text += f"\n...[truncated — file is {total} bytes, showing first {_READ_MAX_BYTES}]"
    return text
