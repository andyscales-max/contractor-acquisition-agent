"""Outreach template + placeholder resolution."""

from __future__ import annotations

import pytest

from contractor_agent.outreach import compose, derive_first_name


def test_first_name_from_contact_field():
    assert derive_first_name({"contact_name": "Jane Doe"}) == "Jane"


def test_first_name_from_email_local_part():
    assert derive_first_name({"email": "john.smith@acme.com"}) == "John"


def test_first_name_from_business_when_personal_branded():
    p = {"business_name": "Carlos Roofing & Repair"}
    assert derive_first_name(p) == "Carlos"


def test_first_name_falls_back_to_there():
    p = {"business_name": "The Best Roofers", "email": "info@x.com"}
    assert derive_first_name(p) == "there"


def test_compose_resolves_all_placeholders():
    p = {
        "business_name": "Acme Roofing",
        "trade": "roofing",
        "city": "Austin, TX",
        "email": "jane@acme.com",
    }
    msg = compose(p, sender_name="Andy")
    assert "Acme Roofing" in msg.body
    assert "roofing" in msg.body
    assert "Austin, TX" in msg.body
    assert "Andy" in msg.body
    assert msg.placeholders["first_name"] == "Jane"


def test_compose_subject_rotates_with_index():
    p = {"business_name": "X", "trade": "roofing", "city": "Y"}
    s0 = compose(p, sender_name="A", subject_index=0).subject
    s1 = compose(p, sender_name="A", subject_index=1).subject
    s2 = compose(p, sender_name="A", subject_index=2).subject
    assert len({s0, s1, s2}) >= 2  # not all identical


def test_compose_uses_trade_label_for_unknown_trade():
    p = {"business_name": "X", "trade": "unknown_trade", "city": "Y"}
    msg = compose(p, sender_name="A")
    assert "construction" in msg.body  # fallback label


def test_compose_handles_missing_fields_gracefully():
    msg = compose({"business_name": "X"}, sender_name="A")
    assert "X" in msg.body
    # No KeyError; body still has placeholders resolved
    assert "{" not in msg.body
