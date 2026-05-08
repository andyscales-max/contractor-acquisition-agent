"""CLI orchestrator — discover, enrich, filter, draft, status.

Usage:
    python -m contractor_agent.cli discover --trade roofing --city "Austin, TX" --limit 50
    python -m contractor_agent.cli enrich [--limit 50]
    python -m contractor_agent.cli filter
    python -m contractor_agent.cli draft [--limit 10] [--dry-run]
    python -m contractor_agent.cli status
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .config import Settings
from .discovery import TRADE_QUERIES, discover
from .enrichment import enrich_prospect
from .gmail_client import GmailDraftService, StubDraftService
from .icp_filter import evaluate_icp
from .ledger import Ledger, new_correlation_id
from .outreach import compose
from .scorer import fit_score


def _setup_logging(verbose: bool) -> str:
    """Return run_id used as a correlation prefix for this CLI invocation."""
    run_id = uuid.uuid4().hex[:8]
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=f"%(asctime)s [run={run_id}] %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return run_id


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_discover(args, settings: Settings) -> int:
    api_key = settings.require_serpapi()
    log = logging.getLogger("discover")

    rows = discover(
        api_key=api_key,
        trade=args.trade,
        city=args.city,
        limit=args.limit,
    )
    log.info("Discovered %s prospects from SerpAPI", len(rows))

    inserted = 0
    updated = 0
    with Ledger(settings.ledger_path) as ledger:
        for row in rows:
            row.pop("_query_used", None)  # not part of the schema
            row["correlation_id"] = new_correlation_id()
            row["status"] = "discovered"
            _, was_new = ledger.upsert_prospect(row)
            if was_new:
                inserted += 1
            else:
                updated += 1
    log.info("Ledger: %s new, %s updated", inserted, updated)
    return 0


def cmd_enrich(args, settings: Settings) -> int:
    log = logging.getLogger("enrich")
    workers = settings.enrichment_workers
    timeout = settings.http_timeout

    with Ledger(settings.ledger_path) as ledger:
        targets = ledger.list_needing_enrichment(limit=args.limit)
        log.info("Enriching %s prospects (workers=%s)", len(targets), workers)

        hits = 0
        misses = 0

        def _work(prospect):
            return prospect, enrich_prospect(
                website=prospect["website"], timeout=timeout
            )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_work, p) for p in targets]
            for fut in as_completed(futures):
                prospect, candidate = fut.result()
                if candidate and candidate.confidence >= 0.55:
                    ledger.set_email(prospect["id"], candidate.email)
                    ledger.update_status(prospect["id"], "enriched")
                    hits += 1
                else:
                    ledger.update_status(prospect["id"], "enriched")
                    misses += 1

    log.info("Enrichment done: %s hits, %s misses", hits, misses)
    return 0


def cmd_filter(args, settings: Settings) -> int:
    log = logging.getLogger("filter")
    qualified = 0
    rejected = 0

    with Ledger(settings.ledger_path) as ledger:
        # Evaluate everything that's been enriched (or discovered, if no website crawl).
        for status in ("enriched", "discovered"):
            for prospect in ledger.list_by_status(status):
                result = evaluate_icp(prospect)
                if result.qualified:
                    score = fit_score(prospect)
                    ledger.set_fit_score(prospect["id"], score)
                    ledger.update_status(prospect["id"], "qualified")
                    qualified += 1
                else:
                    ledger.update_status(
                        prospect["id"], "rejected", rejection_reason=result.reason
                    )
                    rejected += 1

    log.info("Filter done: %s qualified, %s rejected", qualified, rejected)
    return 0


def cmd_draft(args, settings: Settings) -> int:
    log = logging.getLogger("draft")
    sender_email = settings.require_from_email()
    sender_name = settings.from_name or sender_email.split("@", 1)[0].capitalize()

    if args.dry_run:
        service = StubDraftService()
        log.info("DRY RUN — no Gmail drafts will be created")
    else:
        service = GmailDraftService(
            credentials_path=settings.gmail_credentials_path,
            token_path=settings.gmail_token_path,
        )

    drafted = 0
    skipped = 0

    with Ledger(settings.ledger_path) as ledger:
        targets = ledger.list_by_status("qualified", limit=args.limit)
        # Sort by fit score desc when present
        targets.sort(key=lambda p: p.get("fit_score") or 0, reverse=True)

        for idx, prospect in enumerate(targets):
            if not prospect.get("email"):
                skipped += 1
                continue
            msg = compose(prospect, sender_name=sender_name, subject_index=idx)
            from_header = (
                f"{sender_name} <{sender_email}>" if sender_name else sender_email
            )
            try:
                draft_id = service.create_draft(
                    to=prospect["email"],
                    subject=msg.subject,
                    body=msg.body,
                    sender=from_header,
                )
                ledger.set_drafted(prospect["id"], draft_id)
                drafted += 1
                log.info(
                    "drafted: %s → %s (subject=%r)",
                    prospect["business_name"],
                    prospect["email"],
                    msg.subject,
                )
            except Exception as exc:
                log.error("Draft failed for %s: %s", prospect["business_name"], exc)
                skipped += 1

    log.info("Draft done: %s created, %s skipped", drafted, skipped)
    if args.dry_run and isinstance(service, StubDraftService):
        out_path = Path("outputs") / "drafts_dryrun.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(service.calls, f, indent=2)
        log.info("Wrote dry-run drafts to %s", out_path)
    return 0


def cmd_status(args, settings: Settings) -> int:
    with Ledger(settings.ledger_path) as ledger:
        stats = ledger.stats()
    print(json.dumps(stats, indent=2))
    return 0


def cmd_demo(args, settings: Settings) -> int:
    """No-keys-needed sanity check: seed three fake prospects and run a dry-run draft.

    Prints the would-be email so the recipient can verify the install works
    before they bother getting a SerpAPI key or Gmail OAuth set up.
    """
    log = logging.getLogger("demo")
    sender_name = settings.from_name or "You"
    sender_email = settings.from_email or "you@example.com"

    fake_prospects = [
        {
            "place_id": f"demo_{uuid.uuid4().hex[:8]}",
            "business_name": "Carlos Roofing & Repair",
            "trade": "roofing",
            "city": "Austin, TX",
            "phone": "(512) 555-1234",
            "website": "https://example.com",
            "email": "carlos@example.com",
            "rating": 4.8,
            "review_count": 47,
            "fit_score": 92,
            "status": "qualified",
        },
        {
            "place_id": f"demo_{uuid.uuid4().hex[:8]}",
            "business_name": "Hill Country Plumbing",
            "trade": "plumbing",
            "city": "Austin, TX",
            "phone": "(512) 555-9876",
            "website": "https://example.com",
            "email": "info@example.com",
            "rating": 4.6,
            "review_count": 28,
            "fit_score": 78,
            "status": "qualified",
        },
        {
            "place_id": f"demo_{uuid.uuid4().hex[:8]}",
            "business_name": "Lone Star Kitchen & Bath",
            "trade": "kitchen_bath",
            "city": "Austin, TX",
            "phone": "(512) 555-2468",
            "website": "https://example.com",
            "email": "owner@example.com",
            "rating": 5.0,
            "review_count": 19,
            "fit_score": 88,
            "status": "qualified",
        },
    ]

    service = StubDraftService()
    print()
    print("=" * 64)
    print("  DEMO MODE — fake prospects, no API calls")
    print("=" * 64)
    print()

    for idx, prospect in enumerate(fake_prospects):
        msg = compose(prospect, sender_name=sender_name, subject_index=idx)
        service.create_draft(
            to=prospect["email"],
            subject=msg.subject,
            body=msg.body,
            sender=f"{sender_name} <{sender_email}>",
        )
        print(f"--- Prospect {idx + 1}: {prospect['business_name']} "
              f"(fit_score={prospect['fit_score']}) ---")
        print(f"To:      {prospect['email']}")
        print(f"Subject: {msg.subject}")
        print()
        print(msg.body)
        print()

    print("=" * 64)
    print(f"  Demo complete — {len(service.calls)} fake drafts composed.")
    print("  Install is healthy. Ready for real keys + a real run.")
    print("=" * 64)
    print()
    return 0


def cmd_export(args, settings: Settings) -> int:
    """Export a ledger snapshot to CSV for inspection."""
    log = logging.getLogger("export")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id", "correlation_id", "business_name", "trade", "city", "phone",
        "website", "email", "rating", "review_count", "fit_score",
        "status", "rejection_reason", "draft_id", "created_at", "updated_at",
    ]
    with Ledger(settings.ledger_path) as ledger:
        rows = ledger.conn.execute(
            f"SELECT {', '.join(fields)} FROM prospects ORDER BY id"
        ).fetchall()
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow([r[k] for k in fields])
    log.info("Exported %s rows to %s", len(rows), out_path)
    return 0


# ---------------------------------------------------------------------------
# Arg parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="contractor_agent")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("discover", help="Pull contractors from Google Maps")
    pd.add_argument("--trade", required=True, choices=sorted(TRADE_QUERIES.keys()))
    pd.add_argument("--city", required=True, help="e.g., 'Austin, TX'")
    pd.add_argument("--limit", type=int, default=50)
    pd.set_defaults(func=cmd_discover)

    pe = sub.add_parser("enrich", help="Crawl websites for emails")
    pe.add_argument("--limit", type=int, default=None)
    pe.set_defaults(func=cmd_enrich)

    pf = sub.add_parser("filter", help="Apply ICP filter and score")
    pf.set_defaults(func=cmd_filter)

    pdr = sub.add_parser("draft", help="Create Gmail drafts for qualified prospects")
    pdr.add_argument("--limit", type=int, default=10)
    pdr.add_argument("--dry-run", action="store_true",
                     help="Don't hit Gmail API; write outputs/drafts_dryrun.json")
    pdr.set_defaults(func=cmd_draft)

    ps = sub.add_parser("status", help="Print ledger counts by status")
    ps.set_defaults(func=cmd_status)

    px = sub.add_parser("export", help="Dump ledger to CSV")
    px.add_argument("--output", default="outputs/prospects.csv")
    px.set_defaults(func=cmd_export)

    pdemo = sub.add_parser("demo", help="No-keys sanity check (fake prospects)")
    pdemo.set_defaults(func=cmd_demo)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_id = _setup_logging(args.verbose)
    logging.getLogger("cli").info("starting cmd=%s run_id=%s", args.cmd, run_id)
    settings = Settings.from_env()
    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
