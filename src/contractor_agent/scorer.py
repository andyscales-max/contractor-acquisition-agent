"""Fit score 0-100 for a contractor prospect.

Inputs available: rating, review_count, has_email, has_website, trade.
Tunable weights live as module-level constants — adjust to taste.
"""

from __future__ import annotations

from typing import Any, Dict

WEIGHTS = {
    "has_email": 25,        # email reachable via enrichment
    "has_website": 10,      # website present
    "rating": 25,           # scaled from rating
    "review_count": 25,     # scaled by log
    "personal_email": 15,   # not a role inbox
}


def _scale_rating(rating) -> float:
    # 0-5 → 0-1, with 4.0 = 0.6, 5.0 = 1.0, <3.0 = 0
    if rating is None:
        return 0.0
    try:
        r = float(rating)
    except (TypeError, ValueError):
        return 0.0
    if r < 3.0:
        return 0.0
    return min(1.0, (r - 3.0) / 2.0)


def _scale_reviews(count) -> float:
    if count is None:
        return 0.0
    try:
        n = int(count)
    except (TypeError, ValueError):
        return 0.0
    # 0 reviews → 0; 10 reviews → 0.5; 100+ reviews → 1.0
    if n <= 0:
        return 0.0
    if n >= 100:
        return 1.0
    # log-ish piecewise
    if n < 10:
        return n / 20.0  # 0–0.45
    return 0.5 + min(0.5, (n - 10) / 180.0)


def _is_personal_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    local = email.split("@", 1)[0].lower()
    role_locals = {"info", "contact", "office", "hello", "admin", "sales", "support"}
    return local not in role_locals and not local.startswith("noreply")


def fit_score(prospect: Dict[str, Any]) -> int:
    """Return integer 0-100."""
    score = 0.0

    if prospect.get("website"):
        score += WEIGHTS["has_website"]

    email = prospect.get("email") or ""
    if email:
        score += WEIGHTS["has_email"]
        if _is_personal_email(email):
            score += WEIGHTS["personal_email"]

    score += WEIGHTS["rating"] * _scale_rating(prospect.get("rating"))
    score += WEIGHTS["review_count"] * _scale_reviews(prospect.get("review_count"))

    return max(0, min(100, int(round(score))))
