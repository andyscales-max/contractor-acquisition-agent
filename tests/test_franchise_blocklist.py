"""Franchise blocklist matching."""

from __future__ import annotations

import pytest

from contractor_agent.franchise_blocklist import is_franchise


@pytest.mark.parametrize("name,expected_term", [
    ("ServPro of North Austin", "servpro"),
    ("Mr. Handyman of Round Rock", "mr. handyman"),
    ("Roto-Rooter Plumbing", "roto-rooter"),
    ("Bath Fitter Texas", "bath fitter"),
    ("CertaPro Painters of Austin", "certapro"),
    ("TruGreen Lawn Care", "trugreen"),
    ("Budget Blinds of Austin", "budget blinds"),
])
def test_known_franchises_blocked(name, expected_term):
    is_fr, term = is_franchise(name)
    assert is_fr is True
    assert term == expected_term


@pytest.mark.parametrize("name", [
    "Acme Roofing & Repair",
    "Lone Star Construction",
    "Carlos Carpentry",
    "Hill Country Plumbing",
])
def test_independents_pass(name):
    is_fr, term = is_franchise(name)
    assert is_fr is False
    assert term is None


def test_handles_none_input():
    is_fr, term = is_franchise(None)
    assert is_fr is False
