"""Built-in tools that require no external setup."""

import subprocess
from datetime import datetime


def get_datetime() -> str:
    """Return the current date and time."""
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")


def open_application(app_name: str) -> str:
    """Open a macOS application by name (e.g. Safari, Spotify, Terminal)."""
    result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True)
    if result.returncode == 0:
        return f"Opened {app_name}."
    return f"Could not open {app_name}: {result.stderr.strip()}"


TOOLS = [get_datetime, open_application]
