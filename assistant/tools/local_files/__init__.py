"""Local file-manager tools — gated on LOCAL_FILES_DIR.

Only registers when the user has explicitly designated a sandbox folder
in .env.  Without that, the LLM has no way to touch local storage.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TOOLS: list = []

if os.environ.get("LOCAL_FILES_DIR"):
    from .client import list_directory, read_file, search_files, write_file
    TOOLS.extend([list_directory, read_file, write_file, search_files])
