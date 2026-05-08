# Contractor Acquisition Agent

A command-line tool that finds independent contractor businesses (roofers, plumbers, GCs, etc.), filters them against your ICP, and drafts personalized cold outreach to your Gmail. You review and send.

```
discover → enrich → filter → draft
```

The agent **drafts only** — it never sends emails on its own. You review every draft in Gmail before clicking send.

---

## Quick start (5 minutes)

### macOS / Linux

```bash
git clone https://github.com/andyscales-max/contractor-acquisition-agent.git
cd contractor-acquisition-agent
./setup.sh
source .venv/bin/activate
contractor-agent demo
```

### Windows

You'll use **Git Bash** (which comes free with Git for Windows). PowerShell and CMD aren't supported.

1. Install **Git for Windows**: https://git-scm.com/download/win — accept all defaults during install. Git Bash gets installed automatically.
2. Install **Python 3.9+**: https://www.python.org/downloads/windows/ — **important: check "Add Python to PATH" on the first install screen.**
3. Open **Git Bash** (Start Menu → "Git Bash") and run:

   ```bash
   git clone https://github.com/andyscales-max/contractor-acquisition-agent.git
   cd contractor-acquisition-agent
   ./setup.sh
   source .venv/Scripts/activate
   contractor-agent demo
   ```

If `demo` prints three sample emails, your install is healthy. Then proceed to **Real run** below.

---

## What you need

| Thing | Why | Where to get it |
|---|---|---|
| Python 3.9+ | runs the agent | [python.org/downloads](https://www.python.org/downloads/) |
| SerpAPI key | discovers contractors via Google Maps | [serpapi.com](https://serpapi.com) — free tier = 100 searches/mo |
| Gmail account | drafts go here | your existing Gmail |
| `credentials.json` | Gmail OAuth | [Google Cloud Console](https://console.cloud.google.com) — see below |

### Getting `credentials.json` (Gmail OAuth)

You only need this for the `draft` command, not for `discover` / `enrich` / `filter`.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or pick an existing one)
3. **APIs & Services → Library** → enable **Gmail API**
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Application type: **Desktop**
6. Download the JSON, save it as `./credentials.json` in this project's root
7. First time you run `contractor-agent draft`, your browser will open to authorize. The token is saved to `data/gmail_token.json` and reused after that.

> **Note:** the OAuth screen will say "unverified app" because this is your personal tool. Click "Advanced → Go to (unsafe)" — you're authorizing your own software with your own Google account.

---

## Real run

> **Windows users**: replace `source .venv/bin/activate` with `source .venv/Scripts/activate` in any command below.

```bash
source .venv/bin/activate

# 1. Discover 25 roofers in Austin (uses SerpAPI Google Maps)
contractor-agent discover --trade roofing --city "Austin, TX" --limit 25

# 2. Crawl their websites for emails
contractor-agent enrich

# 3. Apply ICP filter (has email + phone + decent reviews + not a national franchise)
contractor-agent filter

# 4. See what you have
contractor-agent status
# {
#   "discovered": 0,
#   "enriched": 0,
#   "qualified": 8,
#   "rejected": 17,
#   "drafted": 0,
#   "sent": 0,
#   "total": 25
# }

# 5. Preview drafts without touching Gmail
contractor-agent draft --limit 5 --dry-run
# (writes outputs/drafts_dryrun.json)

# 6. Real drafts to Gmail (open Gmail → review → send)
contractor-agent draft --limit 5

# 7. Export everything to CSV
contractor-agent export --output outputs/prospects.csv
```

### Trades supported

`general_contractor`, `roofing`, `hvac`, `plumbing`, `electrical`, `kitchen_bath`, `remodeling`, `landscaping`, `painting`, `flooring`, `concrete`, `siding`, `windows_doors`, `pool`

Add more by editing `TRADE_QUERIES` in [`src/contractor_agent/discovery.py`](src/contractor_agent/discovery.py).

---

## Customizing

**Before sending real drafts, edit the email template.** The default body has a `[TODO: replace with your one-line value prop]` marker — fill it in.

| Want to change | Edit |
|---|---|
| Email subject lines / body | [`src/contractor_agent/outreach.py`](src/contractor_agent/outreach.py) |
| Block more national franchises | [`src/contractor_agent/franchise_blocklist.py`](src/contractor_agent/franchise_blocklist.py) |
| ICP thresholds (min reviews, min rating) | [`src/contractor_agent/icp_filter.py`](src/contractor_agent/icp_filter.py) |
| Fit-score weights | [`src/contractor_agent/scorer.py`](src/contractor_agent/scorer.py) |
| Add a trade | `discovery.py` (TRADE_QUERIES) + `contracts/contractor_lead.schema.json` (enum) |

---

## Troubleshooting

**`contractor-agent: command not found`**
You haven't activated the venv. Run `source .venv/bin/activate` (Mac/Linux) or `source .venv/Scripts/activate` (Windows Git Bash) first.

**Windows: `./setup.sh` does nothing or "command not found"**
You're using PowerShell or CMD. Open **Git Bash** instead (it comes with Git for Windows).

**Windows: `python: command not found`**
You skipped "Add Python to PATH" during install. Reinstall Python and check that box, or add Python's install dir to PATH manually.

**`SERPAPI_KEY is not set`**
Edit `.env` and add your key. Get one at [serpapi.com](https://serpapi.com).

**Gmail OAuth screen says "unverified app"**
Expected — this is your personal tool. Click "Advanced → Go to (unsafe)".

**`gmail.compose` scope errors when drafting**
Delete `data/gmail_token.json` and re-run `contractor-agent draft` — it'll re-authorize with the right scopes.

**Enrichment hit rate looks low (under 30%)**
Normal for cold contractors — many small operators don't expose emails on their sites. Options:
- Lower the confidence threshold in `cli.py:cmd_enrich` (currently 0.55)
- Add a SerpAPI email-search step (see "Extending" below)
- Buy a list with emails included for high-value targets

**Tests fail after editing code**
```bash
.venv/bin/pytest -v
```
Read the failure output. Most failures will be in `test_icp_filter.py` or `test_outreach.py` if you tightened thresholds or changed templates.

---

## Architecture

```
src/contractor_agent/
├── config.py             # .env loading
├── ledger.py             # SQLite, dedup by place_id, status FSM
├── discovery.py          # SerpAPI Google Maps wrapper (DI: HttpClient)
├── enrichment.py         # Website crawl → email regex (DI: HttpFetcher)
├── icp_filter.py         # Qualified vs rejected + reasons
├── franchise_blocklist.py  # National franchise names
├── scorer.py             # Fit score 0-100
├── outreach.py           # Template + placeholder resolution
├── gmail_client.py       # OAuth + draft creation (DI: DraftService)
└── cli.py                # Subcommands

contracts/                # JSON schemas (the source of truth for data shapes)
tests/                    # 50 tests — pure-logic modules covered, all DI-friendly
```

External calls (HTTP, Gmail) are dependency-injected so tests run offline. Production paths use `requests` and `google-api-python-client`.

---

## Extending

Things you'll likely want next, in rough order of value:

1. **Customize the email body** — biggest single lever
2. **Add SerpAPI email search** as a fallback when website crawl fails (~+10pp hit rate)
3. **Add a state license-board surface** (TX TDLR or FL DBPR) for higher-quality leads
4. **Add a daily cron** that runs discover + enrich + filter overnight
5. **Add a Slack notification** when fresh qualified prospects appear

The architecture is designed for these — each is a new module that registers a new CLI subcommand.

---

## Development

```bash
# Run tests
.venv/bin/pytest

# Run tests with verbose output
.venv/bin/pytest -v

# Run a single test
.venv/bin/pytest tests/test_outreach.py -v

# Reset ledger (start fresh)
rm data/ledger.db
```

---

## License

MIT — see [LICENSE](LICENSE).
