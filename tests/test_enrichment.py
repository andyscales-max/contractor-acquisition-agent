"""Enrichment regex + candidate ranking. HTTP is mocked via injected fetcher."""

from __future__ import annotations

from typing import Dict, Optional

from contractor_agent.enrichment import enrich_prospect, _extract_candidates


class FakeFetcher:
    def __init__(self, pages: Dict[str, str]):
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, *, timeout: int) -> Optional[str]:
        self.calls.append(url)
        return self.pages.get(url)


def test_extracts_mailto_links():
    html = '<a href="mailto:owner@acme.com">Email us</a>'
    cands = _extract_candidates(html, source_url="https://acme.com", target_domain="acme.com")
    emails = {c.email for c in cands}
    assert "owner@acme.com" in emails


def test_extracts_plain_text_emails():
    html = "Contact us at info@acme.com or call 555-1234"
    cands = _extract_candidates(html, source_url="https://acme.com", target_domain="acme.com")
    assert any(c.email == "info@acme.com" for c in cands)


def test_personal_email_outranks_role():
    html = """
    <p>General: info@acme.com</p>
    <p>Owner: john@acme.com</p>
    """
    cands = _extract_candidates(html, source_url="https://acme.com", target_domain="acme.com")
    by_email = {c.email: c for c in cands}
    assert by_email["john@acme.com"].confidence > by_email["info@acme.com"].confidence


def test_filters_image_assets():
    html = '<img src="logo@2x.png" /> contact: hi@acme.com'
    cands = _extract_candidates(html, source_url="https://acme.com", target_domain="acme.com")
    emails = {c.email for c in cands}
    assert "hi@acme.com" in emails
    assert "logo@2x.png" not in emails


def test_enrich_prospect_returns_best_candidate():
    fetcher = FakeFetcher({
        "https://acme.com": "<html>Owner: jane@acme.com</html>",
    })
    result = enrich_prospect(website="https://acme.com", fetcher=fetcher, timeout=5)
    assert result is not None
    assert result.email == "jane@acme.com"
    assert result.confidence >= 0.85


def test_enrich_falls_through_to_contact_page():
    fetcher = FakeFetcher({
        "https://acme.com": "<html>No email here</html>",
        "https://acme.com/contact": "<html>Reach owner@acme.com</html>",
    })
    result = enrich_prospect(website="https://acme.com", fetcher=fetcher, timeout=5)
    assert result is not None
    assert result.email == "owner@acme.com"


def test_enrich_returns_none_when_no_emails():
    fetcher = FakeFetcher({"https://acme.com": "<html>nothing</html>"})
    result = enrich_prospect(website="https://acme.com", fetcher=fetcher, timeout=5)
    assert result is None


def test_enrich_handles_empty_website():
    assert enrich_prospect(website="", fetcher=FakeFetcher({}), timeout=5) is None


def test_enrich_normalizes_url_without_scheme():
    fetcher = FakeFetcher({"https://acme.com": "<html>x@acme.com</html>"})
    result = enrich_prospect(website="acme.com", fetcher=fetcher, timeout=5)
    assert result is not None
    assert "acme.com" in fetcher.calls[0]
