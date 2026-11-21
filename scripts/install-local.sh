#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WITH_GIS=0
for arg in "$@"; do
  case "$arg" in
    --gis) WITH_GIS=1 ;;
    *) printf 'Unknown option: %s\nUsage: bash scripts/install-local.sh [--gis]\n' "$arg" >&2; exit 2 ;;
  esac
done

if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3.12+ is required. Install Python and rerun this script." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "Detected Python is older than 3.12. Set PYTHON to a Python 3.12+ executable." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "The created virtual environment has no POSIX Python executable." >&2
  echo "Use the Windows installer on Windows, or run this script in Linux, macOS, or Termux." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip
if [ "$WITH_GIS" -eq 1 ]; then
  "$VENV_PYTHON" -m pip install -e '.[pdf,gis]'
else
  "$VENV_PYTHON" -m pip install -e '.[pdf]'
fi

echo
echo "GEOLOGIA installed in: $ROOT_DIR/.venv"
echo "Start it with: bash scripts/start-local.sh"
echo "Optional GIS extra: bash scripts/install-local.sh --gis"
