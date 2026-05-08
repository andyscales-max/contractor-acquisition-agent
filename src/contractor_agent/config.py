"""Settings loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover — dotenv is in requirements
    pass


@dataclass(frozen=True)
class Settings:
    serpapi_key: Optional[str]
    from_email: Optional[str]
    from_name: Optional[str]
    ledger_path: Path
    gmail_credentials_path: Path
    gmail_token_path: Path
    http_timeout: int
    enrichment_workers: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            serpapi_key=os.getenv("SERPAPI_KEY") or None,
            from_email=os.getenv("FROM_EMAIL") or None,
            from_name=os.getenv("FROM_NAME") or None,
            ledger_path=Path(os.getenv("LEDGER_PATH", "data/ledger.db")),
            gmail_credentials_path=Path(
                os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
            ),
            gmail_token_path=Path(
                os.getenv("GMAIL_TOKEN_PATH", "data/gmail_token.json")
            ),
            http_timeout=int(os.getenv("HTTP_TIMEOUT", "10")),
            enrichment_workers=int(os.getenv("ENRICHMENT_WORKERS", "5")),
        )

    def require_serpapi(self) -> str:
        if not self.serpapi_key:
            raise RuntimeError(
                "SERPAPI_KEY is not set. Add it to your .env file."
            )
        return self.serpapi_key

    def require_from_email(self) -> str:
        if not self.from_email:
            raise RuntimeError(
                "FROM_EMAIL is not set. Add it to your .env file."
            )
        return self.from_email
