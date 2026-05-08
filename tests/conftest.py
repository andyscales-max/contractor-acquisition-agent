"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from contractor_agent.ledger import Ledger


@pytest.fixture
def ledger() -> Ledger:
    """In-memory ledger for fast, isolated tests."""
    led = Ledger(":memory:")
    yield led
    led.close()


@pytest.fixture
def sample_prospect() -> dict:
    return {
        "place_id": "ChIJ_test_123",
        "business_name": "Acme Roofing",
        "trade": "roofing",
        "city": "Austin, TX",
        "phone": "(512) 555-1234",
        "website": "https://acmeroofing.com",
        "email": None,
        "rating": 4.8,
        "review_count": 42,
        "address": "123 Main St, Austin, TX",
    }
