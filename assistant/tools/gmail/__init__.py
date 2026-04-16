"""Gmail tool — registered only when credentials are present and deps installed.

Setup: see README.md in this folder.
"""

from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "v-to-work"
_CREDS_PATH = _CONFIG_DIR / "gmail_credentials.json"

# Only register the tool if the Google API client is installed AND the user has
# placed their OAuth client secret at the expected path.  Otherwise the LLM
# simply won't see it — no error, no prompt about Gmail at runtime.
try:
    import googleapiclient  # noqa: F401
    _deps_ok = True
except ImportError:
    _deps_ok = False

if _deps_ok and _CREDS_PATH.exists():
    from .client import send_email
    TOOLS = [send_email]
else:
    TOOLS = []
