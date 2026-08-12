#!/usr/bin/env bash
set -euo pipefail

LABEL="com.stockchecker.app"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"

launchctl unload "$PLIST_PATH" 2>/dev/null || true
rm -f "$PLIST_PATH"

echo "Uninstalled. Background checks stopped."
