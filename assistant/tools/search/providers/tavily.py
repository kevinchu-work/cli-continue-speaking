"""Tavily provider — LLM-optimised search (https://tavily.com).

Free tier: 1000 searches / month, monthly reset.
"""

import json
import os
import urllib.error
import urllib.request

NAME    = "tavily"
ENV_KEY = "TAVILY_API_KEY"

_ENDPOINT = "https://api.tavily.com/search"


def search(query: str) -> str:
    payload = json.dumps({
        "api_key":       os.environ[ENV_KEY],
        "query":         query,
        "search_depth":  "basic",   # 1 credit; "advanced" costs 2
        "include_answer": True,     # Tavily returns a synthesised answer
        "max_results":   3,
    }).encode()

    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    if data.get("answer"):
        return data["answer"]

    snippets = [r.get("content", "") for r in data.get("results", []) if r.get("content")]
    return " ".join(snippets)[:800] if snippets else "No results found."
