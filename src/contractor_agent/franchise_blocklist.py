"""National contractor franchise blocklist.

ICP is independent operators. Anything matching this list is auto-rejected.

Edit this file to tune for your campaign — keep names lowercased.
"""

from __future__ import annotations

import re
from typing import Optional

# Normalized to lowercase. Match is substring against business_name lowered.
FRANCHISE_NAMES = {
    # Restoration / cleanup
    "servpro",
    "servicemaster",
    "stanley steemer",
    "1-800-water-damage",
    "paul davis restoration",
    "belfor",
    "rainbow international",

    # Handyman
    "mr. handyman",
    "ace handyman",
    "handyman connection",
    "handyman matters",

    # Plumbing
    "roto-rooter",
    "mr. rooter",
    "benjamin franklin plumbing",
    "rooter-man",

    # HVAC
    "one hour heating",
    "aire serv",
    "horizon services",

    # Electrical
    "mr. electric",

    # Appliance / misc
    "mr. appliance",

    # Bath / kitchen
    "bath fitter",
    "re-bath",
    "rebath",
    "miracle method",
    "kitchen tune-up",

    # Painting
    "five star painting",
    "certapro",
    "wow 1 day painting",

    # Windows / blinds / doors
    "budget blinds",
    "window genie",
    "renewal by andersen",
    "champion windows",
    "pella windows",

    # Outdoor / lawn
    "trugreen",
    "lawn doctor",
    "lawn pride",
    "weed man",
    "mosquito joe",
    "scotts lawn",

    # Roofing
    "tuff shed",  # not roofing but national chain
    "1-800-hansons",

    # Concrete / surfaces
    "garage living",
    "garage experts",

    # Other large national chains
    "home depot",
    "lowes",
    "lowe's",
    "ace hardware",
}

# Phrases that signal national/franchise even if name isn't on the list above.
FRANCHISE_PHRASES = (
    "nationwide",
    "locations across the country",
    "find a location near you",
    "franchise opportunities",
    "franchising",
)


def is_franchise(business_name: Optional[str], website_text: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Return (is_franchise, matched_term)."""
    name = (business_name or "").lower()
    for term in FRANCHISE_NAMES:
        if term in name:
            return True, term

    if website_text:
        text = website_text.lower()
        for phrase in FRANCHISE_PHRASES:
            if phrase in text:
                # Extra guard: only flag if name also looks branded
                if re.search(r"\b(inc|llc|corp|services|group)\b", name):
                    return True, phrase

    return False, None
