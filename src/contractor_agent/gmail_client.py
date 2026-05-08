"""Gmail OAuth + draft creation.

First run: opens browser for consent, writes token to GMAIL_TOKEN_PATH.
Subsequent runs: reuses + auto-refreshes the token.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

# We only need draft creation for MVP. Add gmail.send later if you want
# the agent to send unattended.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]


class DraftService(Protocol):
    def create_draft(self, *, to: str, subject: str, body: str, sender: str) -> str: ...


class GmailDraftService:
    """Wraps the Gmail API. Lazy-initializes the service on first use."""

    def __init__(self, *, credentials_path: Path, token_path: Path):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._service = None

    def _build_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds: Optional[Credentials] = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Gmail token at %s", self.token_path)
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found at {self.credentials_path}. "
                        "Download OAuth client (Desktop) from Google Cloud Console "
                        "and place it at this path."
                    )
                logger.info(
                    "No valid Gmail token; launching browser flow with %s",
                    self.credentials_path,
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.info("Saved Gmail token to %s", self.token_path)

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _ensure(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def create_draft(self, *, to: str, subject: str, body: str, sender: str) -> str:
        """Create a Gmail draft. Returns the draft id."""
        service = self._ensure()
        message = MIMEText(body)
        message["to"] = to
        message["from"] = sender
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        draft_id = draft.get("id", "")
        logger.info("Created draft %s for %s", draft_id, to)
        return draft_id


class StubDraftService:
    """No-op service for --dry-run. Records calls for inspection."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_draft(self, *, to: str, subject: str, body: str, sender: str) -> str:
        self.calls.append(
            {"to": to, "subject": subject, "body": body, "sender": sender}
        )
        return f"dryrun-{len(self.calls)}"
