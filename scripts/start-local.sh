#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${GEOLOGIA_PORT:-8000}"
API_BIN="$ROOT_DIR/.venv/bin/geologia-api"

case "$PORT" in
  ''|*[!0-9]*) echo "GEOLOGIA_PORT must be a numeric TCP port." >&2; exit 2 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "GEOLOGIA_PORT must be between 1 and 65535." >&2
  exit 2
fi
if [ ! -x "$API_BIN" ]; then
  echo "GEOLOGIA is not installed. Run: bash scripts/install-local.sh" >&2
  exit 1
fi

echo "GEOLOGIA is bound to localhost only."
echo "Open http://127.0.0.1:$PORT"
exec "$API_BIN" --host 127.0.0.1 --port "$PORT"
