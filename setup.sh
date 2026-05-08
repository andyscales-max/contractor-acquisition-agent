#!/usr/bin/env bash
# One-command setup for contractor-acquisition-agent.
# Idempotent — safe to re-run.

set -e

# Colors (off if not a TTY)
if [ -t 1 ]; then
    G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; B='\033[0;34m'; N='\033[0m'
else
    G=''; Y=''; R=''; B=''; N=''
fi

ok()    { printf "${G}✓${N} %s\n" "$1"; }
warn()  { printf "${Y}!${N} %s\n" "$1"; }
fail()  { printf "${R}✗${N} %s\n" "$1"; exit 1; }
info()  { printf "${B}→${N} %s\n" "$1"; }

cd "$(dirname "$0")"

echo
echo "================================================================"
echo "  Contractor Acquisition Agent — Setup"
echo "================================================================"
echo

# 1. Python version check
info "Checking Python version..."
if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 not found. Install Python 3.9+ from https://www.python.org/downloads/"
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')
if [ "$PY_OK" != "1" ]; then
    fail "Python 3.9+ required (you have $PY_VER). Install from https://www.python.org/downloads/"
fi
ok "Python $PY_VER"

# 2. Virtual env
if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv .venv
    ok "Created .venv/"
else
    ok ".venv/ already exists"
fi

# 3. Install package
info "Installing dependencies (this can take a minute)..."
.venv/bin/pip install --quiet --upgrade pip setuptools wheel >/dev/null
.venv/bin/pip install --quiet -e ".[dev]" >/dev/null
ok "Package installed (editable mode)"

# 4. Run tests so user knows install is healthy
info "Running test suite..."
if .venv/bin/pytest --quiet >/dev/null 2>&1; then
    ok "All tests pass"
else
    warn "Some tests failed — try: .venv/bin/pytest"
fi

# 5. Configure .env
echo
echo "----------------------------------------------------------------"
echo "  Configuration (.env)"
echo "----------------------------------------------------------------"
if [ -f ".env" ]; then
    warn ".env already exists — leaving it alone."
    info "  Edit it manually if you need to change keys."
else
    cp .env.example .env

    echo
    read -r -p "SerpAPI key (paste, or press Enter to skip): " SERPAPI_KEY_INPUT
    if [ -n "$SERPAPI_KEY_INPUT" ]; then
        # macOS BSD sed needs '' after -i
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^SERPAPI_KEY=.*|SERPAPI_KEY=$SERPAPI_KEY_INPUT|" .env
        else
            sed -i "s|^SERPAPI_KEY=.*|SERPAPI_KEY=$SERPAPI_KEY_INPUT|" .env
        fi
        ok "SerpAPI key saved to .env"
    else
        warn "Skipped — add SERPAPI_KEY to .env before running 'discover'"
    fi

    read -r -p "Gmail address you'll send from: " FROM_EMAIL_INPUT
    if [ -n "$FROM_EMAIL_INPUT" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^FROM_EMAIL=.*|FROM_EMAIL=$FROM_EMAIL_INPUT|" .env
        else
            sed -i "s|^FROM_EMAIL=.*|FROM_EMAIL=$FROM_EMAIL_INPUT|" .env
        fi
        ok "FROM_EMAIL saved to .env"
    fi

    read -r -p "Your name (used in email signature): " FROM_NAME_INPUT
    if [ -n "$FROM_NAME_INPUT" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^FROM_NAME=.*|FROM_NAME=$FROM_NAME_INPUT|" .env
        else
            sed -i "s|^FROM_NAME=.*|FROM_NAME=$FROM_NAME_INPUT|" .env
        fi
        ok "FROM_NAME saved to .env"
    fi
fi

# 6. Gmail credentials reminder
echo
echo "----------------------------------------------------------------"
echo "  Gmail OAuth"
echo "----------------------------------------------------------------"
if [ -f "credentials.json" ]; then
    ok "credentials.json found"
else
    warn "credentials.json NOT found (you only need this for the 'draft' command)"
    info "  1. Go to https://console.cloud.google.com/"
    info "  2. APIs & Services → Credentials → Create OAuth client ID"
    info "  3. Application type: Desktop"
    info "  4. Download JSON, save as ./credentials.json"
    info "  5. First 'draft' run will open your browser to authorize"
fi

# 7. Done
echo
echo "================================================================"
ok "Setup complete!"
echo "================================================================"
echo
info "Try a no-keys-needed demo:"
echo "    source .venv/bin/activate"
echo "    contractor-agent demo"
echo
info "Real run (needs SerpAPI key):"
echo "    contractor-agent discover --trade roofing --city \"Austin, TX\" --limit 25"
echo "    contractor-agent enrich"
echo "    contractor-agent filter"
echo "    contractor-agent status"
echo "    contractor-agent draft --limit 5 --dry-run    # safe preview"
echo
