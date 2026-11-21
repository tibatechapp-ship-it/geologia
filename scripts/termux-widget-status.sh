#!/usr/bin/env bash
set -euo pipefail

PORT="${GEOLOGIA_PORT:-8000}"
PROJECT_DIR="${GEOLOGIA_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "GEOLOGIA is not installed."
  exit 1
fi
if "$PYTHON_BIN" - "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 <<'PY'
import json
import sys
from urllib.request import urlopen

payload = json.load(urlopen(sys.argv[1], timeout=2))
raise SystemExit(0 if payload.get("service") == "geologia" else 1)
PY
then
  echo "GEOLOGIA is running at http://127.0.0.1:$PORT"
else
  echo "GEOLOGIA is not responding at http://127.0.0.1:$PORT"
  exit 1
fi
