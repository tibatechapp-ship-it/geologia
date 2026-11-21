#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="$HOME/.geologia"
PID_FILE="$DATA_DIR/geologia-api.pid"
if [ ! -f "$PID_FILE" ]; then
  echo "No GEOLOGIA PID file found."
  exit 0
fi
PID="$(cat "$PID_FILE" 2>/dev/null || true)"
case "$PID" in
  ''|*[!0-9]*) rm -f "$PID_FILE"; echo "Removed invalid PID file."; exit 0 ;;
esac
if ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "GEOLOGIA was not running; removed stale PID file."
  exit 0
fi

CMDLINE=""
if [ -r "/proc/$PID/cmdline" ]; then
  CMDLINE="$(tr '\0' ' ' < "/proc/$PID/cmdline")"
fi
case "$CMDLINE" in
  *geologia-api*) ;;
  *)
    echo "PID $PID is not identifiable as geologia-api; refusing to terminate it." >&2
    rm -f "$PID_FILE"
    exit 1
    ;;
esac

kill -TERM "$PID"
for attempt in $(seq 1 20); do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "GEOLOGIA stopped."
    exit 0
  fi
  sleep 0.5
done
kill -KILL "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "GEOLOGIA stopped after forced shutdown."
