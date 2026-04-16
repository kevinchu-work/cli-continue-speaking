# Web Search Tool

Gives the assistant real web search.  Unlike the old DuckDuckGo Instant
Answer API (which only covers Wikipedia-style entities), this tool delivers
synthesised answers for current events, weather, news, prices, facts — any
time-sensitive or open-domain question.

The tool is **provider-agnostic**: pick any supported backend, drop its API
key into `.env`, and the tool auto-registers.  When more than one provider
is configured, choose between them with `SEARCH_PROVIDER`.

Once set up, you can say things like:
- *"What's the weather in Hong Kong?"*
- *"Who won the F1 race yesterday?"*
- *"What's the price of Bitcoin right now?"*

---

## Supported providers

Active backends live in `providers/`.  Today: **Tavily**.

| Provider | Free tier | Resets? | Notes |
|---|---|---|---|
| [Tavily](https://tavily.com) | 1000 / month | monthly | LLM-optimised — returns a synthesised answer |

More providers are easy to add (Brave, Serper, SearXNG, …) — see
*[Adding a new provider](#adding-a-new-provider)* below.

---

## Setup

### 1. Pick a provider and get an API key

**Tavily** (recommended):
1. Sign up at <https://tavily.com> (Google / GitHub / email).
2. Copy the API key from the dashboard (starts with `tvly-...`).
3. 1000 free searches/month, resets monthly, no credit card.

### 2. Add the key to `.env`

```bash
echo 'TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxx' >> .env
```

### 3. (Optional) Pin a preferred provider

If you have keys for several providers, pick which one wins:

```bash
echo 'SEARCH_PROVIDER=tavily' >> .env
```

If `SEARCH_PROVIDER` is unset, the first provider with a configured key is
used (order defined in `providers/__init__.py`).

---

## Adding a new provider

1. Create `providers/<name>.py` exposing three top-level names:
   ```python
   NAME    = "brave"                           # lowercase identifier
   ENV_KEY = "BRAVE_SEARCH_API_KEY"            # env var holding the key

   def search(query: str) -> str:
       """Call the provider and return a short answer string."""
       ...
   ```
2. Append the module to `ALL` in `providers/__init__.py`:
   ```python
   from . import tavily, brave
   ALL = [tavily, brave]
   ```

That's it — no changes to `client.py`, `__init__.py`, or anywhere else.
The tool stays the same from the LLM's perspective.

### Provider ideas

| Provider | Free tier | Endpoint |
|---|---|---|
| [Brave Search](https://brave.com/search/api/) | 2000 / month | `api.search.brave.com/res/v1/web/search` |
| [Serper](https://serper.dev) | 2500 one-time | `google.serper.dev/search` |
| [SearXNG](https://docs.searxng.org/) | unlimited (self-host) | your own instance |

---

## Security notes

- API keys go in `.env` (gitignored), never commit.
- Each provider's key is read-only and scoped to search — leaking one only
  lets someone burn your search quota.
- Rotate or revoke on the provider's dashboard.

---

## Troubleshooting

**Tool not appearing to the LLM** — confirm a provider key is loaded:
```bash
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from assistant.tools.search.providers import ALL
import os
for p in ALL:
    print(f'{p.NAME}: {\"configured\" if os.environ.get(p.ENV_KEY) else \"missing key\"}')"
```

**`Search failed via tavily: HTTP 401`** — invalid or expired key.

**`Search failed via tavily: HTTP 429`** — monthly free-tier limit reached.
Either wait for reset or add a second provider and switch via
`SEARCH_PROVIDER`.
