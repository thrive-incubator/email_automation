#!/usr/bin/env bash
# Step 2 — Open the Console pages for the OAuth consent screen + client ID.
#
# These two things CANNOT be created with gcloud for a Gmail user-consent app,
# so this script just opens the right pages for the active project and prints
# the exact values to paste. Follow GMAIL_SETUP.md alongside it.
set -euo pipefail

PROJECT_ID="${1:-${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}}"

if [ -z "${PROJECT_ID:-}" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "✗ No project set. Run ./01-create-project.sh first, or pass one:" >&2
  echo "    ./02-open-oauth-console.sh my-project-id" >&2
  exit 1
fi

CONSENT_URL="https://console.cloud.google.com/auth/overview?project=$PROJECT_ID"
CLIENTS_URL="https://console.cloud.google.com/auth/clients?project=$PROJECT_ID"

echo "▸ Project: $PROJECT_ID"
echo ""
echo "  1) Consent screen : $CONSENT_URL"
echo "  2) OAuth clients  : $CLIENTS_URL"
echo ""
echo "  When creating the OAuth client (type: Web application), paste this exact"
echo "  Authorized redirect URI (it is hardcoded in backend/app/routers/auth.py):"
echo ""
echo "    http://localhost:8008/api/auth/gmail/callback"
echo ""
echo "  Then download the JSON and save it to:"
echo "    backend/data/client_secret.json"
echo ""

# open in the default browser (macOS `open`, Linux `xdg-open`)
OPEN_CMD=""
if command -v open >/dev/null 2>&1; then OPEN_CMD="open";
elif command -v xdg-open >/dev/null 2>&1; then OPEN_CMD="xdg-open"; fi

if [ -n "$OPEN_CMD" ]; then
  read -r -p "Open both pages in your browser now? [y/N] " reply
  if [[ "$reply" =~ ^[Yy]$ ]]; then
    "$OPEN_CMD" "$CONSENT_URL"
    "$OPEN_CMD" "$CLIENTS_URL"
  fi
fi

echo "✓ After downloading client_secret.json, run ./03-verify.sh"
