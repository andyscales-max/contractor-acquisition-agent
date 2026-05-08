"""Discover contractor prospects via SerpAPI Google Maps.

DI-first: caller passes an HTTP-callable; default uses requests.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional, Protocol

import requests

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

# Trade → list of Google Maps query terms.
# Add or refine these for your campaign.
TRADE_QUERIES: Dict[str, List[str]] = {
    "general_contractor": [
        "general contractor",
        "home builder",
        "construction company",
    ],
    "roofing": [
        "roofing contractor",
        "roofer",
        "roof repair",
    ],
    "hvac": [
        "hvac contractor",
        "heating and cooling",
        "air conditioning installation",
    ],
    "plumbing": [
        "plumber",
        "plumbing contractor",
    ],
    "electrical": [
        "electrician",
        "electrical contractor",
    ],
    "kitchen_bath": [
        "kitchen remodeling",
        "bathroom remodeling",
        "kitchen and bath",
    ],
    "remodeling": [
        "home remodeling",
        "home renovation",
        "remodeling contractor",
    ],
    "landscaping": [
        "landscaping contractor",
        "landscape design",
    ],
    "painting": [
        "painting contractor",
        "house painter",
    ],
    "flooring": [
        "flooring contractor",
        "hardwood flooring installation",
    ],
    "concrete": [
        "concrete contractor",
        "concrete services",
    ],
    "siding": [
        "siding contractor",
        "siding installation",
    ],
    "windows_doors": [
        "window contractor",
        "door installation",
        "window replacement",
    ],
    "pool": [
        "pool builder",
        "swimming pool contractor",
    ],
}


class HttpClient(Protocol):
    def get(self, url: str, params: Dict, timeout: int) -> requests.Response: ...


class _RequestsClient:
    def get(self, url: str, params: Dict, timeout: int) -> requests.Response:
        return requests.get(url, params=params, timeout=timeout)


def _call_serpapi(
    api_key: str,
    query: str,
    city: str,
    *,
    http: HttpClient,
    timeout: int,
    retries: int = 3,
) -> Dict:
    params = {
        "engine": "google_maps",
        "type": "search",
        "q": query,
        "api_key": api_key,
        "hl": "en",
        "google_domain": "google.com",
        "z": "13",
    }
    if city:
        params["location"] = city

    backoff = 2
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = http.get(SERPAPI_URL, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(
                "SerpAPI non-200 (attempt %s): %s — %s",
                attempt,
                resp.status_code,
                resp.text[:200],
            )
        except Exception as exc:
            last_err = exc
            logger.warning("SerpAPI request failed on attempt %s: %s", attempt, exc)

        if attempt < retries:
            time.sleep(backoff)
            backoff *= 2

    raise RuntimeError(f"SerpAPI failed after {retries} attempts: {last_err}")


def _parse_local_results(data: Dict, *, query_used: str, trade: str, city: str) -> List[Dict]:
    out: List[Dict] = []
    local = data.get("local_results") or data.get("places_results") or []
    for r in local:
        name = r.get("title") or r.get("name")
        if not name:
            continue
        reviews = r.get("reviews")
        if isinstance(reviews, dict):
            review_count = reviews.get("count")
        else:
            review_count = reviews
        out.append(
            {
                "place_id": r.get("place_id") or r.get("place_id_token"),
                "business_name": name,
                "trade": trade,
                "city": city,
                "phone": r.get("phone") or "",
                "website": r.get("website") or "",
                "rating": r.get("rating"),
                "review_count": review_count,
                "address": r.get("address") or "",
                "_query_used": query_used,
            }
        )
    return out


def discover(
    *,
    api_key: str,
    trade: str,
    city: str,
    limit: int = 50,
    http: Optional[HttpClient] = None,
    timeout: int = 30,
) -> List[Dict]:
    """Discover contractor prospects for one trade in one city.

    Returns a list of prospect dicts ready for Ledger.upsert_prospect().
    Deduplicated within this call by place_id (or business_name+address fallback).
    """
    if trade not in TRADE_QUERIES:
        raise ValueError(
            f"Unknown trade {trade!r}. Known trades: {sorted(TRADE_QUERIES)}"
        )
    queries = TRADE_QUERIES[trade]
    http = http or _RequestsClient()

    seen: set[str] = set()
    results: List[Dict] = []

    for query in queries:
        if len(results) >= limit:
            break
        logger.info("SerpAPI: trade=%s query=%r city=%r", trade, query, city)
        data = _call_serpapi(api_key, query, city, http=http, timeout=timeout)
        for p in _parse_local_results(data, query_used=query, trade=trade, city=city):
            key = p.get("place_id") or f"{p['business_name']}|{p.get('address','')}"
            if key in seen:
                continue
            seen.add(key)
            results.append(p)
            if len(results) >= limit:
                break

    logger.info(
        "Discovered %s unique prospects for trade=%s city=%s", len(results), trade, city
    )
    return results
