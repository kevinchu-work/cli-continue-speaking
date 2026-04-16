"""Web-search dispatcher — routes to whichever provider is configured.

Selection order:
    1. The provider named by SEARCH_PROVIDER (if set and valid).
    2. The first provider in providers.ALL whose API key is present.
"""

import os

from .providers import ALL

_BY_NAME = {p.NAME: p for p in ALL}


def _pick_provider():
    preferred = os.environ.get("SEARCH_PROVIDER", "").lower()
    if preferred in _BY_NAME and os.environ.get(_BY_NAME[preferred].ENV_KEY):
        return _BY_NAME[preferred]
    for p in ALL:
        if os.environ.get(p.ENV_KEY):
            return p
    return None


def web_search(query: str) -> str:
    """Search the web and return a concise answer.

    Use this for current events, weather, news, prices, specific facts,
    anything time-sensitive, or any question the assistant doesn't know
    from its training data.

    Args:
        query: Natural-language search query.

    Returns:
        A short answer, or an error description.
    """
    provider = _pick_provider()
    if provider is None:
        return ("Search is not configured — set an API key for one of: "
                + ", ".join(p.NAME for p in ALL))
    try:
        return provider.search(query)
    except Exception as e:
        return f"Search failed via {provider.NAME}: {e}"
