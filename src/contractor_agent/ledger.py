"""SQLite ledger for contractor prospects.

DI-first: callers pass a path (or ":memory:") at construction. No globals.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT NOT NULL UNIQUE,
    place_id TEXT UNIQUE,
    business_name TEXT NOT NULL,
    trade TEXT,
    city TEXT,
    state TEXT,
    phone TEXT,
    website TEXT,
    email TEXT,
    contact_name TEXT,
    rating REAL,
    review_count INTEGER,
    address TEXT,
    fit_score INTEGER,
    status TEXT NOT NULL DEFAULT 'discovered',
    rejection_reason TEXT,
    draft_id TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_trade ON prospects(trade);
CREATE INDEX IF NOT EXISTS idx_prospects_email ON prospects(email);
"""

VALID_STATUSES = {
    "discovered",
    "enriched",
    "qualified",
    "rejected",
    "drafted",
    "sent",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_correlation_id() -> str:
    return f"lead-{uuid.uuid4()}"


class Ledger:
    """Thin SQLite wrapper. All callers must close() or use as a context manager."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------ writes

    def upsert_prospect(self, row: Dict[str, Any]) -> tuple[int, bool]:
        """Insert if new (by place_id); update existing fields otherwise.

        Returns (rowid, inserted) where inserted=True means newly created.
        """
        place_id = row.get("place_id")
        existing = None
        if place_id:
            existing = self.conn.execute(
                "SELECT id FROM prospects WHERE place_id = ?", (place_id,)
            ).fetchone()

        if existing:
            updated = self._merge_update(existing["id"], row)
            return existing["id"], False

        cid = row.get("correlation_id") or new_correlation_id()
        created = now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO prospects (
                correlation_id, place_id, business_name, trade, city, state,
                phone, website, email, contact_name, rating, review_count,
                address, fit_score, status, rejection_reason, draft_id, sent_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                place_id,
                row["business_name"],
                row.get("trade"),
                row.get("city"),
                row.get("state"),
                row.get("phone"),
                row.get("website"),
                row.get("email"),
                row.get("contact_name"),
                row.get("rating"),
                row.get("review_count"),
                row.get("address"),
                row.get("fit_score"),
                row.get("status", "discovered"),
                row.get("rejection_reason"),
                row.get("draft_id"),
                row.get("sent_at"),
                created,
                created,
            ),
        )
        self.conn.commit()
        return cur.lastrowid, True

    def _merge_update(self, prospect_id: int, row: Dict[str, Any]) -> bool:
        """Update only the fields present and non-empty in `row`."""
        updatable = {
            "business_name", "trade", "city", "state", "phone", "website",
            "email", "contact_name", "rating", "review_count", "address",
            "fit_score", "status", "rejection_reason", "draft_id", "sent_at",
        }
        sets = []
        values: List[Any] = []
        for key, value in row.items():
            if key in updatable and value not in (None, ""):
                sets.append(f"{key} = ?")
                values.append(value)
        if not sets:
            return False
        sets.append("updated_at = ?")
        values.append(now_iso())
        values.append(prospect_id)
        self.conn.execute(
            f"UPDATE prospects SET {', '.join(sets)} WHERE id = ?", values
        )
        self.conn.commit()
        return True

    def update_status(
        self, prospect_id: int, status: str, *, rejection_reason: Optional[str] = None
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        self.conn.execute(
            "UPDATE prospects SET status = ?, rejection_reason = ?, updated_at = ? WHERE id = ?",
            (status, rejection_reason, now_iso(), prospect_id),
        )
        self.conn.commit()

    def set_email(self, prospect_id: int, email: str, contact_name: Optional[str] = None) -> None:
        self.conn.execute(
            "UPDATE prospects SET email = ?, contact_name = COALESCE(?, contact_name), updated_at = ? WHERE id = ?",
            (email, contact_name, now_iso(), prospect_id),
        )
        self.conn.commit()

    def set_fit_score(self, prospect_id: int, score: int) -> None:
        self.conn.execute(
            "UPDATE prospects SET fit_score = ?, updated_at = ? WHERE id = ?",
            (score, now_iso(), prospect_id),
        )
        self.conn.commit()

    def set_drafted(self, prospect_id: int, draft_id: str) -> None:
        self.conn.execute(
            "UPDATE prospects SET status = 'drafted', draft_id = ?, updated_at = ? WHERE id = ?",
            (draft_id, now_iso(), prospect_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------- reads

    def get(self, prospect_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT * FROM prospects WHERE id = ?", (prospect_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_by_status(self, status: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM prospects WHERE status = ? ORDER BY id"
        params: tuple = (status,)
        if limit:
            sql += " LIMIT ?"
            params = (status, limit)
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def list_needing_enrichment(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = (
            "SELECT * FROM prospects WHERE email IS NULL "
            "AND website IS NOT NULL AND website != '' "
            "AND status IN ('discovered', 'enriched') ORDER BY id"
        )
        params: tuple = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def stats(self) -> Dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM prospects GROUP BY status"
        ).fetchall()
        out = {s: 0 for s in VALID_STATUSES}
        out["total"] = 0
        for r in rows:
            out[r["status"]] = r["n"]
            out["total"] += r["n"]
        return out

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


@contextmanager
def open_ledger(path: str | Path) -> Iterator[Ledger]:
    ledger = Ledger(path)
    try:
        yield ledger
    finally:
        ledger.close()
