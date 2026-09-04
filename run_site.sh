#!/usr/bin/env bash
# Start both the FastAPI backend and the Vite frontend for kindred-path2college.
# Ctrl-C stops both.
set -e
cd "$(dirname "$0")"

# --- backend ---
echo "Starting API on http://localhost:8000 ..."
/usr/local/bin/python3 -m uvicorn api_server:app --port 8000 &
API_PID=$!

# --- frontend ---
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 18 >/dev/null 2>&1 || true

cd web
[ -d node_modules ] || npm install
echo "Starting web on http://localhost:5173 ..."
npm run dev &
WEB_PID=$!

trap "echo; echo 'Stopping...'; kill $API_PID $WEB_PID 2>/dev/null" EXIT INT TERM
wait
