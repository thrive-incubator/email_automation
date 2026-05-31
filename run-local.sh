#!/usr/bin/env bash
# One command to run Inbox Autopilot locally: backend (FastAPI :8008) + frontend (Vite :5180).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Kill anything already bound to our ports (e.g. a stale prior run). We only touch
# :8008 and :5180 — never your other dev servers on different ports.
free_port() {
  local port=$1
  local pids
  pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "▸ Freeing port $port (killing PID(s): $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}
free_port 8008
free_port 5180

echo "▸ Setting up backend…"
cd "$BACKEND"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  created backend/.env from .env.example — add your API keys there."
fi

echo "▸ Setting up frontend…"
cd "$FRONTEND"
if [ ! -d node_modules ]; then
  npm install
fi

echo "▸ Starting servers…"
cd "$BACKEND"
./venv/bin/uvicorn app.main:app --reload --port 8008 &
BACKEND_PID=$!

cd "$FRONTEND"
npm run dev -- --port 5180 &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "▸ Shutting down…"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "  Backend  → http://localhost:8008  (docs: /docs)"
echo "  Frontend → http://localhost:5180"
echo "  Ctrl+C to stop."
echo ""

wait
