"""ICP filter qualifications + rejections."""

from __future__ import annotations

import pytest

from contractor_agent.icp_filter import evaluate_icp


def _base() -> dict:
    return {
        "business_name": "Best Roofing Co",
        "website": "https://best.com",
        "phone": "5125551234",
        "email": "owner@best.com",
        "rating": 4.5,
        "review_count": 30,
    }


def test_qualified_baseline():
    result = evaluate_icp(_base())
    assert result.qualified is True
    assert result.reason is None


def test_rejected_no_website():
    p = _base()
    p["website"] = ""
    result = evaluate_icp(p)
    assert result.qualified is False
    assert result.reason == "no_website"


def test_rejected_no_phone():
    p = _base()
    p["phone"] = ""
    assert evaluate_icp(p).reason == "no_phone"


def test_rejected_no_email():
    p = _base()
    p["email"] = ""
    assert evaluate_icp(p).reason == "no_email_after_enrichment"


def test_rejected_franchise_servpro():
    p = _base()
    p["business_name"] = "Servpro of North Austin"
    result = evaluate_icp(p)
    assert result.qualified is False
    assert result.reason.startswith("franchise_match:")


def test_rejected_low_rating():
    p = _base()
    p["rating"] = 2.9
    assert "low_rating" in evaluate_icp(p).reason


def test_rejected_low_review_count():
    p = _base()
    p["review_count"] = 2
    assert "low_review_count" in evaluate_icp(p).reason


def test_qualified_when_rating_missing():
    """Missing data shouldn't auto-reject — only present-but-bad data."""
    p = _base()
    p["rating"] = None
    p["review_count"] = None
    assert evaluate_icp(p).qualified is True
