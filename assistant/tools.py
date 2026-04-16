"""LLM-callable tools: datetime, open app, web search."""

import json
import subprocess
import urllib.request
import urllib.parse
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


def web_search(query: str) -> str:
    """Search the web and return a brief answer using DuckDuckGo."""
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
        "q": query, "format": "json", "no_html": "1", "skip_disambig": "1"
    })
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        answer = (data.get("AbstractText")
                  or data.get("Answer")
                  or (data.get("RelatedTopics") or [{}])[0].get("Text", ""))
        return answer or "No direct answer found."
    except Exception as e:
        return f"Search failed: {e}"


TOOLS = [get_datetime, open_application, web_search]
