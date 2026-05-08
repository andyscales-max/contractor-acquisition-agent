"""Email template + placeholder resolution.

Edit DEFAULT_SUBJECTS and DEFAULT_BODY to match your offer. The CLI passes
prospect dicts to `compose()`; missing placeholders fall back to safe defaults.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# CUSTOMIZE THESE FOR YOUR CAMPAIGN
# ---------------------------------------------------------------------------

DEFAULT_SUBJECTS: List[str] = [
    "Quick question about {business_name}",
    "{first_name} — quick idea for {business_name}",
    "Helping {trade_label} pros in {city}",
]

# {first_name}, {business_name}, {trade_label}, {city}, {sender_name}
DEFAULT_BODY = """Hi {first_name},

I came across {business_name} while researching top {trade_label} pros in {city}. Your reviews stood out.

I help independent {trade_label} businesses [TODO: replace with your one-line value prop — e.g., "book 15-25 qualified residential jobs per month without paying HomeAdvisor / Angi lead fees"].

Worth a 15-min call this week to see if there's a fit?

— {sender_name}
"""

TRADE_LABELS: Dict[str, str] = {
    "general_contractor": "general contracting",
    "roofing": "roofing",
    "hvac": "HVAC",
    "plumbing": "plumbing",
    "electrical": "electrical",
    "kitchen_bath": "kitchen & bath remodeling",
    "remodeling": "remodeling",
    "landscaping": "landscaping",
    "painting": "painting",
    "flooring": "flooring",
    "concrete": "concrete",
    "siding": "siding",
    "windows_doors": "window & door",
    "pool": "pool building",
}


@dataclass(frozen=True)
class ComposedMessage:
    subject: str
    body: str
    placeholders: Dict[str, str]


_ROLE_LOCALS = {
    "info", "contact", "office", "hello", "admin", "sales", "support",
    "team", "service", "estimates", "quotes", "marketing", "noreply",
}


def _first_name_from_email(email: str) -> Optional[str]:
    if not email or "@" not in email:
        return None
    local = email.split("@", 1)[0].lower()
    # firstname.lastname → firstname
    candidate = re.split(r"[._\-]", local, maxsplit=1)[0]
    if candidate in _ROLE_LOCALS:
        return None
    if candidate.isalpha() and 2 <= len(candidate) <= 20:
        return candidate.capitalize()
    return None


def _first_name_from_business(business_name: str) -> Optional[str]:
    """If business name starts with a person's name, extract it."""
    if not business_name:
        return None
    first_word = business_name.split()[0].strip("'.,")
    # Heuristic: capitalized, alphabetic, not a generic word
    if first_word.isalpha() and first_word[0].isupper() and len(first_word) >= 3:
        bad = {"The", "A", "An", "Best", "Top", "Premier", "Elite", "Pro", "All",
               "American", "United", "Allied", "First", "Quality"}
        if first_word not in bad:
            return first_word
    return None


def derive_first_name(prospect: Dict[str, Any]) -> str:
    if prospect.get("contact_name"):
        return str(prospect["contact_name"]).split()[0].capitalize()
    by_email = _first_name_from_email(prospect.get("email") or "")
    if by_email:
        return by_email
    by_biz = _first_name_from_business(prospect.get("business_name") or "")
    if by_biz:
        return by_biz
    return "there"


def compose(
    prospect: Dict[str, Any],
    *,
    sender_name: str,
    subject_template: Optional[str] = None,
    body_template: Optional[str] = None,
    subject_index: int = 0,
) -> ComposedMessage:
    placeholders = {
        "first_name": derive_first_name(prospect),
        "business_name": prospect.get("business_name") or "your business",
        "trade_label": TRADE_LABELS.get(
            prospect.get("trade") or "", "construction"
        ),
        "city": prospect.get("city") or "your area",
        "sender_name": sender_name,
    }

    subj_tpl = subject_template or DEFAULT_SUBJECTS[
        subject_index % len(DEFAULT_SUBJECTS)
    ]
    body_tpl = body_template or DEFAULT_BODY

    subject = subj_tpl.format(**placeholders)
    body = body_tpl.format(**placeholders)
    return ComposedMessage(subject=subject, body=body, placeholders=placeholders)
