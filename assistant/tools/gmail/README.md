# Gmail Tool

Enables the assistant to send email on your behalf via the Gmail API.

Once set up, you can say things like:
- *"Email alice@example.com and tell her I'll be late"*
- *"Send a note to my dad saying happy birthday"*

The tool is **auto-registered**: the LLM only sees it when both the Python
dependencies are installed and your OAuth credentials are in place.  Skip this
setup entirely and the assistant just won't have email capability.

---

## Setup (one-time, ~5 minutes)

### 1. Install the optional dependencies

```bash
uv sync --extra gmail
```

This adds `google-api-python-client`, `google-auth-httplib2`, and
`google-auth-oauthlib`.

### 2. Create a Google Cloud OAuth client

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or pick an existing one).
3. **Enable the Gmail API**:
   APIs & Services → Library → search "Gmail API" → Enable.
4. **Configure the OAuth consent screen**:
   - User type: **External** (unless you're on a Workspace domain).
   - App name: anything (e.g. "Voice Assistant").
   - User support email: your email.
   - Developer contact: your email.
   - Scopes: click **Add or remove scopes** and add `.../auth/gmail.send`.
   - Test users: add your own Gmail address.
5. **Create OAuth credentials**:
   - APIs & Services → Credentials → Create Credentials → **OAuth client ID**.
   - Application type: **Desktop app**.
   - Download the JSON file.

### 3. Place the credentials file

```bash
mkdir -p ~/.config/v-to-work
mv ~/Downloads/client_secret_*.json ~/.config/v-to-work/gmail_credentials.json
```

### 4. First-run authorisation

The next time you launch the assistant and it tries to send an email, a browser
window will open for OAuth consent.  Approve the `gmail.send` scope.  The
granted token is cached at:

```
~/.config/v-to-work/gmail_token.json
```

Subsequent runs use the cached token and refresh it silently.

---

## Security notes

- The scope used is `gmail.send` only — the tool **cannot read your inbox**.
- The token file grants the ability to send email as you; treat it like a
  password.  `~/.config/v-to-work/` is not committed to git.
- Revoke access anytime at
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

---

## Troubleshooting

**"Access blocked: authorisation error"** — you haven't added your own email
as a Test User in the OAuth consent screen.

**"This app isn't verified"** — expected for personal Desktop apps.  Click
*Advanced → Go to [your app] (unsafe)* since you are the developer.

**Tool not appearing to the LLM** — check both:
```bash
ls ~/.config/v-to-work/gmail_credentials.json  # must exist
uv run python -c "import googleapiclient"       # must import clean
```
