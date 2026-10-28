#!/bin/bash
# Install or update the WhatsApp → Obsidian sync.
#
#   ./install.sh                  plain sync (no network use at all)
#   ./install.sh --voice          + local voice-note transcription (Apple Silicon)
#   ./install.sh --summaries      + daily Claude summaries
#
# Safe to run again: it rebuilds the venv packages and reloads the schedule.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
LABEL="local.whatsapp-vault-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
INTERVAL="${INTERVAL:-900}"  # seconds between runs

if [ ! -x .venv/bin/python ]; then
  "${PYTHON:-python3}" -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
pkgs=()
for arg in "$@"; do
  case "$arg" in
    --voice) pkgs+=(mlx-whisper imageio-ffmpeg) ;;
    --summaries) pkgs+=(anthropic) ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done
if [ ${#pkgs[@]} -gt 0 ]; then
  .venv/bin/pip install -q --upgrade "${pkgs[@]}"
fi

if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "Created config.json. Set \"vault\" to the Obsidian vault folder, then run ./install.sh again."
  exit 0
fi

if ! .venv/bin/python wa_sync.py --doctor; then
  echo "Fix the problems above, then run ./install.sh again."
  exit 1
fi

mkdir -p logs "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/.venv/bin/python</string>
    <string>$DIR/wa_sync.py</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/sync.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/sync.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

REAL_PY="$(.venv/bin/python -c 'import os, sys; print(os.path.realpath(sys.executable))')"
cat <<EOF

Scheduled: runs every $((INTERVAL / 60)) min. Log: $DIR/logs/sync.log

One manual step. The background job needs Full Disk Access to read WhatsApp's data:
  System Settings → Privacy & Security → Full Disk Access → "+" → press Cmd+Shift+G and paste:
  $REAL_PY
Then switch it on and run:  launchctl kickstart -k gui/$(id -u)/$LABEL ; sleep 5 ; tail logs/sync.log
EOF
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles" 2>/dev/null || true
