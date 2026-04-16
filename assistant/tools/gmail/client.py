"""Gmail client — send emails via the Gmail API with OAuth2."""

import base64
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_CONFIG_DIR = Path.home() / ".config" / "v-to-work"
_TOKEN_PATH = _CONFIG_DIR / "gmail_token.json"
_CREDS_PATH = _CONFIG_DIR / "gmail_credentials.json"

_service = None  # cached across calls


def _get_service():
    """Return an authenticated Gmail service, running OAuth flow on first use."""
    global _service
    if _service is not None:
        return _service

    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_PATH), _SCOPES)
            creds = flow.run_local_server(port=0)
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _TOKEN_PATH.write_text(creds.to_json())

    _service = build("gmail", "v1", credentials=creds)
    return _service


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Subject line of the email.
        body: Plain-text body of the email.

    Returns:
        Confirmation with the sent message ID, or an error description.
    """
    try:
        service = _get_service()
        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["Subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return f"Email sent to {to} (id: {result['id']})."
    except Exception as e:
        return f"Failed to send email: {e}"
