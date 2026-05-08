# Contractor Acquisition Agent — Claude Rules

## Non-negotiables
- Contracts-first: define schemas for all structured outputs and integrations.
- DI-first: external calls (HTTP, Gmail) must be injectable/mocked in tests.
- Test-first: new behavior requires tests when feasible.
- Observability: every CLI run logs a `run_id` and key counters; every prospect has a `correlation_id`.

## Repo context
- Python project, pytest layout under `tests/`.
- Source under `src/contractor_agent/` (run with `pythonpath=src`).
- SQLite ledger at `data/ledger.db` (configurable via `LEDGER_PATH`).
- Contracts live in `contracts/` (JSON Schema draft-07).

## Pipeline shape
```
discover (SerpAPI) → ledger:discovered
  → enrich (website crawl) → ledger:enriched (+email)
    → filter (ICP rules + scorer) → ledger:qualified | rejected
      → draft (Gmail API) → ledger:drafted
```

## When making changes
- Adding a new trade: extend `TRADE_QUERIES` in `discovery.py` AND the `trade` enum in `contracts/contractor_lead.schema.json`.
- Adding a franchise to block: edit `franchise_blocklist.py`. Lowercase substrings.
- Tuning ICP: edit `MIN_REVIEW_COUNT` / `MIN_RATING` in `icp_filter.py` or weights in `scorer.py`.
- Editing copy: `outreach.py`. Keep placeholder names stable (`first_name`, `business_name`, `trade_label`, `city`, `sender_name`).
