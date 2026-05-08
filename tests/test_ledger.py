"""Ledger insert / dedup / status transitions."""

from __future__ import annotations

import pytest

from contractor_agent.ledger import Ledger, new_correlation_id


def test_correlation_id_format():
    cid = new_correlation_id()
    assert cid.startswith("lead-")
    # 36-char UUID after the prefix
    assert len(cid) == len("lead-") + 36


def test_insert_creates_row(ledger: Ledger, sample_prospect: dict):
    pid, was_new = ledger.upsert_prospect(sample_prospect)
    assert was_new is True
    row = ledger.get(pid)
    assert row["business_name"] == "Acme Roofing"
    assert row["status"] == "discovered"
    assert row["correlation_id"].startswith("lead-")


def test_dedup_by_place_id(ledger: Ledger, sample_prospect: dict):
    pid1, was_new1 = ledger.upsert_prospect(sample_prospect)
    # Same place_id, different name → should update, not insert
    sample_prospect["business_name"] = "Acme Roofing & Solar"
    pid2, was_new2 = ledger.upsert_prospect(sample_prospect)

    assert pid1 == pid2
    assert was_new1 is True
    assert was_new2 is False
    row = ledger.get(pid1)
    assert row["business_name"] == "Acme Roofing & Solar"


def test_set_email_and_status(ledger: Ledger, sample_prospect: dict):
    pid, _ = ledger.upsert_prospect(sample_prospect)
    ledger.set_email(pid, "owner@acmeroofing.com")
    ledger.update_status(pid, "enriched")
    row = ledger.get(pid)
    assert row["email"] == "owner@acmeroofing.com"
    assert row["status"] == "enriched"


def test_invalid_status_rejected(ledger: Ledger, sample_prospect: dict):
    pid, _ = ledger.upsert_prospect(sample_prospect)
    with pytest.raises(ValueError):
        ledger.update_status(pid, "bogus_status")


def test_list_needing_enrichment_filters_correctly(ledger: Ledger):
    ledger.upsert_prospect({
        "place_id": "p1", "business_name": "Has site no email",
        "website": "https://a.com", "trade": "roofing",
    })
    ledger.upsert_prospect({
        "place_id": "p2", "business_name": "No site",
        "website": "", "trade": "roofing",
    })
    ledger.upsert_prospect({
        "place_id": "p3", "business_name": "Already enriched",
        "website": "https://c.com", "email": "x@c.com", "trade": "roofing",
    })
    targets = ledger.list_needing_enrichment()
    names = {t["business_name"] for t in targets}
    assert names == {"Has site no email"}


def test_stats_counts_by_status(ledger: Ledger, sample_prospect: dict):
    pid, _ = ledger.upsert_prospect(sample_prospect)
    ledger.update_status(pid, "qualified")
    s = ledger.stats()
    assert s["qualified"] == 1
    assert s["total"] == 1
