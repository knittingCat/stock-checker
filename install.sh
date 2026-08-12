#!/usr/bin/env bash
# Installs the stock checker as a macOS background job (launchd agent).
# Wakes every 10 minutes; stock_checker.py itself throttles actual site
# fetches to config.json's check_interval_minutes.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3)"
LABEL="com.stockchecker.app"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [ -z "$PYTHON_BIN" ]; then
    echo "python3 not found on PATH. Install Python 3 first." >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/config.json" ]; then
    echo "No config.json found. Run 'python3 setup.py' first to set the product URL." >&2
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

sed -e "s#__PYTHON__#${PYTHON_BIN}#g" \
    -e "s#__REPO_DIR__#${REPO_DIR}#g" \
    -e "s#__LABEL__#${LABEL}#g" \
    "$REPO_DIR/com.stockchecker.plist.template" > "$PLIST_PATH"

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed and running as a background job."
echo "Logs: $REPO_DIR/stock_checker.log"
echo "To stop it: ./uninstall.sh"
