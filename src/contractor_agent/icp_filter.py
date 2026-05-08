"""ICP filter — qualify or reject contractor prospects.

Rules-based MVP. Returns (qualified, reason) so reject reasons are auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .franchise_blocklist import is_franchise


@dataclass(frozen=True)
class IcpResult:
    qualified: bool
    reason: Optional[str] = None  # rejection reason; None if qualified


# Tunable ICP thresholds — edit these to suit your campaign.
MIN_REVIEW_COUNT = 5
MIN_RATING = 3.5


def evaluate_icp(prospect: Dict[str, Any]) -> IcpResult:
    """Apply ICP rules. Returns IcpResult."""

    name = prospect.get("business_name") or ""
    website = (prospect.get("website") or "").strip()
    phone = (prospect.get("phone") or "").strip()
    email = (prospect.get("email") or "").strip()
    rating = prospect.get("rating")
    review_count = prospect.get("review_count")

    # Hard requirements
    if not website:
        return IcpResult(False, "no_website")
    if not phone:
        return IcpResult(False, "no_phone")
    if not email:
        return IcpResult(False, "no_email_after_enrichment")

    # Franchise / national chain
    is_fr, term = is_franchise(name)
    if is_fr:
        return IcpResult(False, f"franchise_match:{term}")

    # Quality bar
    if rating is not None and rating < MIN_RATING:
        return IcpResult(False, f"low_rating:{rating}")
    if review_count is not None and review_count < MIN_REVIEW_COUNT:
        return IcpResult(False, f"low_review_count:{review_count}")

    return IcpResult(True)
