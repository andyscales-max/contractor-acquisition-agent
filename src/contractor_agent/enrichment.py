"""Enrich prospects by crawling their website for emails.

Strategy chain (cheap → expensive):
  1. Fetch homepage; regex emails + mailto links.
  2. If none found, try /contact, /about, /contact-us.
  3. Score each candidate; pick highest. Personal-name emails outrank role inboxes.

DI-first: pass an HTTP fetcher; default uses requests.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Protocol
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

ROLE_LOCAL_PARTS = {
    "info", "contact", "office", "hello", "admin", "sales", "support",
    "team", "service", "estimates", "quotes", "marketing",
}

CONTACT_PATHS = ("/contact", "/contact-us", "/about", "/about-us", "/get-a-quote")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class EmailCandidate:
    email: str
    source_url: str
    is_role: bool
    matched_domain: bool

    @property
    def confidence(self) -> float:
        # Personal email at the company's own domain is highest.
        if not self.is_role and self.matched_domain:
            return 0.90
        if not self.is_role:
            return 0.55  # personal email at a different domain (e.g., gmail)
        if self.is_role and self.matched_domain:
            return 0.65
        return 0.30


class HttpFetcher(Protocol):
    def get(self, url: str, *, timeout: int) -> Optional[str]: ...


class _RequestsFetcher:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def get(self, url: str, *, timeout: int) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                return resp.text
            logger.debug("Non-HTML or non-200 from %s: %s", url, resp.status_code)
        except Exception as exc:
            logger.debug("Fetch failed for %s: %s", url, exc)
        return None


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.lower().lstrip("www.")
    except Exception:
        return ""


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _extract_candidates(html: str, *, source_url: str, target_domain: str) -> List[EmailCandidate]:
    found: dict[str, EmailCandidate] = {}

    # mailto links first — most reliable.
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href^='mailto:']"):
        href = a.get("href", "")
        addr = href.split("mailto:", 1)[-1].split("?", 1)[0].strip().lower()
        if EMAIL_RE.fullmatch(addr):
            found[addr] = _make_candidate(addr, source_url, target_domain)

    # Plain text regex.
    for match in EMAIL_RE.finditer(html):
        addr = match.group(0).lower()
        if addr in found:
            continue
        # Filter out obvious noise (image asset names, etc.)
        if any(addr.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
            continue
        found[addr] = _make_candidate(addr, source_url, target_domain)

    return list(found.values())


def _make_candidate(email: str, source_url: str, target_domain: str) -> EmailCandidate:
    local, _, domain = email.partition("@")
    is_role = local in ROLE_LOCAL_PARTS or local.startswith("noreply")
    matched = bool(target_domain) and domain.endswith(target_domain)
    return EmailCandidate(
        email=email, source_url=source_url, is_role=is_role, matched_domain=matched
    )


def enrich_prospect(
    *,
    website: str,
    fetcher: Optional[HttpFetcher] = None,
    timeout: int = 10,
) -> Optional[EmailCandidate]:
    """Crawl a prospect's website and return the best email candidate, or None."""
    if not website:
        return None

    fetcher = fetcher or _RequestsFetcher()
    base = _normalize_url(website)
    target_domain = _domain_of(base)

    pages_to_try = [base] + [urljoin(base, p) for p in CONTACT_PATHS]
    all_candidates: List[EmailCandidate] = []

    for url in pages_to_try:
        html = fetcher.get(url, timeout=timeout)
        if not html:
            continue
        cands = _extract_candidates(html, source_url=url, target_domain=target_domain)
        all_candidates.extend(cands)

        # Early exit if we have a high-confidence personal email at matched domain.
        best_so_far = max(all_candidates, key=lambda c: c.confidence, default=None)
        if best_so_far and best_so_far.confidence >= 0.85:
            return best_so_far

    if not all_candidates:
        return None
    return max(all_candidates, key=lambda c: c.confidence)
