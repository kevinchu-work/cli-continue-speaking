"""Aggregate all LLM-callable tools.

Each sub-module exposes its own ``TOOLS`` list.  Tools that require external
credentials (Gmail, Discord, etc.) gracefully disable themselves when their
setup is missing, so only configured tools are registered with the LLM.

To add a new tool category:
    1. Create ``assistant/tools/<name>/`` with ``__init__.py`` exposing ``TOOLS``
    2. Import and extend below
    3. Add a README.md in the sub-folder describing setup
"""

import functools
import time
import traceback

from .core import TOOLS as _core_tools
from .gmail import TOOLS as _gmail_tools
from .discord import TOOLS as _discord_tools
from .search import TOOLS as _search_tools


def _wrap(fn):
    """Wrap a tool so its invocation, duration, and any exception are visible.

    Without this, a tool call disappears into the genai SDK's automatic
    function-calling machinery — the user sees "Thinking..." stall with no
    idea whether a tool is running, how long it's taking, or whether it
    silently errored.  The wrapper also turns raw Python exceptions into
    an "ERROR ..." string the LLM can quote back to the user per the
    system prompt, instead of crashing the whole turn.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        args_preview = ", ".join(
            [repr(a) for a in args]
            + [f"{k}={v!r}" for k, v in kwargs.items()]
        )
        print(f"  [tool] {fn.__name__}({args_preview})", flush=True)
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            dt = time.monotonic() - t0
            # One-line preview so the terminal stays readable
            preview = (result if isinstance(result, str) else repr(result))
            preview = preview.replace("\n", " ⏎ ")
            if len(preview) > 160:
                preview = preview[:157] + "..."
            print(f"  [tool] {fn.__name__} → {dt:.2f}s  {preview}", flush=True)
            return result
        except Exception as e:
            dt = time.monotonic() - t0
            tb = traceback.format_exc()
            print(f"  [tool] {fn.__name__} RAISED {dt:.2f}s  {type(e).__name__}: {e}", flush=True)
            print(tb, flush=True)
            # Return the error as a string so the LLM can quote it.  Raising
            # here would bubble up through send_message and kill the turn.
            return f"ERROR in {fn.__name__}: {type(e).__name__}: {e}"
    return wrapper


_all = _core_tools + _gmail_tools + _discord_tools + _search_tools
TOOLS = [_wrap(t) for t in _all]
