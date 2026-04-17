"""Local file writing tool — gated on LOCAL_FILES_DIR.

Only registers when the user has explicitly designated a writable root
folder in .env.  Without that, the LLM has no way to touch local storage.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TOOLS: list = []

if os.environ.get("LOCAL_FILES_DIR"):
    from .client import read_local_file, write_local_file
    TOOLS.extend([write_local_file, read_local_file])
