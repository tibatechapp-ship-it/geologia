#!/usr/bin/env bash
set -euo pipefail

if [ -z "${TERMUX_VERSION:-}" ] || ! command -v pkg >/dev/null 2>&1; then
  echo "This bootstrap is intended for Termux on Android." >&2
  echo "For Linux or macOS, use: bash scripts/install-local.sh" >&2
  exit 2
fi

echo "Installing the build tools needed by Python packages on Android."
echo "The Rust toolchain is used only when native Python dependencies need compilation."
pkg update -y
pkg install -y python git clang rust make pkg-config

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
bash scripts/install-local.sh

SHORTCUTS_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS_DIR"
{
  printf '#!/usr/bin/env bash\n'
  printf 'export GEOLOGIA_PROJECT_DIR=%q\n' "$ROOT_DIR"
  printf 'exec bash %q\n' "$ROOT_DIR/scripts/termux-widget-start.sh"
} > "$SHORTCUTS_DIR/GEOLOGIA"
chmod 700 "$SHORTCUTS_DIR/GEOLOGIA"

echo
echo "GEOLOGIA is installed locally."
echo "Start in a terminal: bash scripts/start-local.sh"
echo "Optional one-tap launcher: install the Termux:Widget app, then add the GEOLOGIA shortcut."
echo "Stop: bash scripts/termux-widget-stop.sh"
echo "Keep the API bound to 127.0.0.1; do not expose it to the network."
