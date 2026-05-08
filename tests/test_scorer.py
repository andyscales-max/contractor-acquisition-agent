"""Fit score behavior."""

from __future__ import annotations

import pytest

from contractor_agent.scorer import fit_score


def test_empty_prospect_scores_zero():
    assert fit_score({}) == 0


def test_high_quality_prospect_scores_high():
    p = {
        "website": "https://acme.com",
        "email": "jane@acme.com",  # personal
        "rating": 4.9,
        "review_count": 200,
    }
    assert fit_score(p) >= 90


def test_role_email_scores_lower_than_personal():
    base = {
        "website": "https://acme.com",
        "rating": 4.5,
        "review_count": 50,
    }
    role = {**base, "email": "info@acme.com"}
    personal = {**base, "email": "jane@acme.com"}
    assert fit_score(personal) > fit_score(role)


def test_low_rating_scores_lower():
    high = {"website": "x", "email": "a@x.com", "rating": 5.0, "review_count": 100}
    low = {"website": "x", "email": "a@x.com", "rating": 3.2, "review_count": 100}
    assert fit_score(high) > fit_score(low)


def test_score_within_bounds():
    """Should never go negative or above 100."""
    extremes = [
        {},
        {"website": "x", "email": "a@x.com", "rating": 5.0, "review_count": 99999},
        {"website": "x", "email": "info@x.com", "rating": 0.0, "review_count": 0},
    ]
    for p in extremes:
        s = fit_score(p)
        assert 0 <= s <= 100


def test_handles_string_numeric_inputs():
    """Defensive: rating/review_count may come in as strings from CSV."""
    p = {"website": "x", "email": "a@x.com", "rating": "4.5", "review_count": "20"}
    s = fit_score(p)
    assert s > 0
