#!/usr/bin/env bash
# Step 3 — Verify everything is wired up before you click "Connect Gmail".
#
# Checks: Gmail API enabled · client_secret.json present & well-formed ·
# .env set to the gmail provider with a sender. Read-only; changes nothing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
SECRET_FILE="$BACKEND/data/client_secret.json"
ENV_FILE="$BACKEND/.env"

PROJECT_ID="${1:-${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}"
fail=0

echo "▸ Project: ${PROJECT_ID:-<none>}"
echo ""

# 1. Gmail API enabled
if gcloud services list --enabled --project="$PROJECT_ID" \
     --filter="config.name:gmail.googleapis.com" --format="value(config.name)" 2>/dev/null \
     | grep -q gmail; then
  echo "  ✓ Gmail API enabled"
else
  echo "  ✗ Gmail API NOT enabled — run ./01-create-project.sh"; fail=1
fi

# 2. client_secret.json present and looks like an OAuth client
if [ -f "$SECRET_FILE" ]; then
  if grep -q '"client_id"' "$SECRET_FILE" && grep -q '"redirect_uris"' "$SECRET_FILE"; then
    echo "  ✓ client_secret.json present at backend/data/"
    if grep -q 'localhost:8008/api/auth/gmail/callback' "$SECRET_FILE"; then
      echo "  ✓ redirect URI matches the app"
    else
      echo "  ⚠ redirect URI not found in client_secret.json — make sure you added"
      echo "      http://localhost:8008/api/auth/gmail/callback in the Console"
    fi
  else
    echo "  ✗ client_secret.json present but missing client_id/redirect_uris"; fail=1
  fi
else
  echo "  ✗ Missing $SECRET_FILE — download it in step 2 (Console)"; fail=1
fi

# 3. .env configured
if [ -f "$ENV_FILE" ]; then
  if grep -qE '^EMAIL_PROVIDER=gmail' "$ENV_FILE"; then
    echo "  ✓ EMAIL_PROVIDER=gmail"
  else
    echo "  ✗ EMAIL_PROVIDER is not 'gmail' in backend/.env"; fail=1
  fi
  if grep -qE '^GMAIL_SENDER=.+' "$ENV_FILE"; then
    echo "  ✓ GMAIL_SENDER set"
  else
    echo "  ⚠ GMAIL_SENDER is empty in backend/.env — set your sending address"
  fi
else
  echo "  ✗ backend/.env not found — run ./run-local.sh once (it copies .env.example)"; fail=1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "✓ All set. Start the app (./run-local.sh) and click 'Connect Gmail' on Settings."
else
  echo "✗ Some checks failed — fix the ✗ items above, then re-run ./03-verify.sh"
  exit 1
fi
