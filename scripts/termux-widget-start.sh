#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GEOLOGIA_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${GEOLOGIA_PORT:-8000}"
DATA_DIR="$HOME/.geologia"
PID_FILE="$DATA_DIR/geologia-api.pid"
LOG_FILE="$DATA_DIR/geologia-api.log"
API_BIN="$ROOT_DIR/.venv/bin/geologia-api"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
BASE_URL="http://127.0.0.1:$PORT"

case "$PORT" in
  ''|*[!0-9]*) echo "GEOLOGIA_PORT must be a numeric TCP port." >&2; exit 2 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "GEOLOGIA_PORT must be between 1 and 65535." >&2
  exit 2
fi
if [ ! -x "$API_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "GEOLOGIA is not installed. Run scripts/install-termux.sh first." >&2
  exit 1
fi
mkdir -p "$DATA_DIR"

is_geologia_healthy() {
  "$PYTHON_BIN" -c 'import json,sys,urllib.request; data=json.load(urllib.request.urlopen(sys.argv[1],timeout=1)); raise SystemExit(0 if data.get("service") == "geologia" else 1)' "$BASE_URL/health" >/dev/null 2>&1
}

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if case "$OLD_PID" in ''|*[!0-9]*) false ;; *) true ;; esac && kill -0 "$OLD_PID" 2>/dev/null; then
    if is_geologia_healthy; then
      echo "GEOLOGIA is already running at $BASE_URL"
      if command -v termux-open-url >/dev/null 2>&1; then
        termux-open-url "$BASE_URL" || true
      fi
      exit 0
    fi
    echo "A GEOLOGIA process is recorded but its health endpoint is not responding." >&2
    echo "Review $LOG_FILE or stop it with scripts/termux-widget-stop.sh." >&2
    exit 1
  fi
  rm -f "$PID_FILE"
fi

nohup "$API_BIN" --host 127.0.0.1 --port "$PORT" >>"$LOG_FILE" 2>&1 </dev/null &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"

for attempt in $(seq 1 60); do
  if is_geologia_healthy; then
    echo "GEOLOGIA is running at $BASE_URL"
    if command -v termux-open-url >/dev/null 2>&1; then
      termux-open-url "$BASE_URL" || true
    else
      echo "Open this address in your browser: $BASE_URL"
    fi
    if command -v termux-notification >/dev/null 2>&1; then
      termux-notification --title "GEOLOGIA" --content "Local workspace ready at $BASE_URL" || true
    fi
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "GEOLOGIA stopped during startup. Recent log:" >&2
    tail -n 40 "$LOG_FILE" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "GEOLOGIA is still starting; check $LOG_FILE." >&2
exit 1
