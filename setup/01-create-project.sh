#!/usr/bin/env bash
# Step 1 — Create the dedicated GCP project and enable the Gmail API.
#
# This is the only fully-scriptable part. The OAuth consent screen and OAuth
# client ID must be created in the Console (see 02-open-oauth-console.sh and
# GMAIL_SETUP.md) — gcloud cannot create a Gmail user-consent OAuth client.
#
# Usage:
#   ./01-create-project.sh                 # uses defaults below, prompts to confirm
#   PROJECT_ID=my-id ./01-create-project.sh
#   ./01-create-project.sh my-id
set -euo pipefail

# ── config (override via env or first arg) ────────────────────────────────────
ORG_ID="${ORG_ID:-362695193512}"                       # thrive-incubator.com org
PROJECT_ID="${1:-${PROJECT_ID:-studio-email-automation}}"      # must be globally unique, 6-30 chars
PROJECT_NAME="${PROJECT_NAME:-Email Automation Studio}"

# ── preflight ─────────────────────────────────────────────────────────────────
if ! command -v gcloud >/dev/null 2>&1; then
  echo "✗ gcloud not found. Install the Google Cloud SDK first." >&2
  exit 1
fi

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
  echo "✗ Not authenticated. Run:  gcloud auth login" >&2
  exit 1
fi

ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)"

echo "▸ Plan:"
echo "    Account     : $ACCOUNT"
echo "    Org         : $ORG_ID"
echo "    Project ID  : $PROJECT_ID"
echo "    Project name: $PROJECT_NAME"
echo ""
read -r -p "Proceed? [y/N] " reply
[[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# ── 1. create project (skip if it already exists) ─────────────────────────────
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "▸ Project '$PROJECT_ID' already exists — skipping create."
else
  echo "▸ Creating project '$PROJECT_ID'…"
  gcloud projects create "$PROJECT_ID" \
    --name="$PROJECT_NAME" \
    --organization="$ORG_ID"
fi

# ── 2. set as active project ──────────────────────────────────────────────────
echo "▸ Setting active project to '$PROJECT_ID'…"
gcloud config set project "$PROJECT_ID" >/dev/null

# ── 3. enable Gmail API (free, no billing required) ───────────────────────────
echo "▸ Enabling gmail.googleapis.com…"
gcloud services enable gmail.googleapis.com --project="$PROJECT_ID"

# ── 4. verify ─────────────────────────────────────────────────────────────────
echo ""
echo "▸ Verifying:"
gcloud services list --enabled --project="$PROJECT_ID" \
  --filter="config.name:gmail.googleapis.com" \
  --format="value(config.name)" | sed 's/^/    enabled: /'

echo ""
echo "✓ Done. Next: run ./02-open-oauth-console.sh to set up the OAuth client."
echo "  (Project '$PROJECT_ID' is now your active gcloud project.)"
