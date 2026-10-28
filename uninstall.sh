#!/bin/bash
# Stop the scheduled sync. Notes already in the vault are left untouched.
set -euo pipefail
LABEL="local.whatsapp-vault-sync"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Stopped. Vault notes, config.json and state.json were kept."
