#!/usr/bin/env bash
set -euo pipefail

PORT="${GEOLOGIA_PORT:-8000}"
PYTHON_BIN="${GEOLOGIA_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "GEOLOGIA is not installed."
  exit 1
fi
if "$PYTHON_BIN" -c 'import json,sys,urllib.request; data=json.load(urllib.request.urlopen(sys.argv[1],timeout=2)); raise SystemExit(0 if data.get("service") == "geologia" else 1)' "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "GEOLOGIA is running at http://127.0.0.1:$PORT"
else
  echo "GEOLOGIA is not responding at http://127.0.0.1:$PORT"
  exit 1
fi
