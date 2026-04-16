"""Registry of available search providers.

To add a new provider:
    1. Create providers/<name>.py exposing module-level NAME, ENV_KEY,
       and a search(query: str) -> str function.
    2. Import and append it to ALL below.
"""

from . import tavily

ALL = [tavily]
