"""Aggregate all LLM-callable tools.

Each sub-module exposes its own ``TOOLS`` list.  Tools that require external
credentials (Gmail, Discord, etc.) gracefully disable themselves when their
setup is missing, so only configured tools are registered with the LLM.

To add a new tool category:
    1. Create ``assistant/tools/<name>/`` with ``__init__.py`` exposing ``TOOLS``
    2. Import and extend below
    3. Add a README.md in the sub-folder describing setup
"""

from .core import TOOLS as _core_tools
from .gmail import TOOLS as _gmail_tools
from .discord import TOOLS as _discord_tools
# from .search import TOOLS as _search_tools   # disabled for now

TOOLS = _core_tools + _gmail_tools + _discord_tools
