"""Web search tool — registered when at least one provider is configured.

Supports multiple backends via a provider abstraction (see ``providers/``).
Setup: see README.md in this folder.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from .providers import ALL

if any(os.environ.get(p.ENV_KEY) for p in ALL):
    from .client import web_search
    TOOLS = [web_search]
else:
    TOOLS = []
