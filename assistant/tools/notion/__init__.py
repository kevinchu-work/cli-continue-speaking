"""Notion tool — append notes to a single page, read it back.

Auto-registers only when both NOTION_TOKEN and NOTION_PAGE_ID are set,
so a partial setup doesn't confuse the LLM with a tool that can't work.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TOOLS: list = []

if os.environ.get("NOTION_TOKEN") and os.environ.get("NOTION_PAGE_ID"):
    from .client import append_to_notion, create_notion_subpage, read_notion_page
    TOOLS.extend([append_to_notion, read_notion_page, create_notion_subpage])
