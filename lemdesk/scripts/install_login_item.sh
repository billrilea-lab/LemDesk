#!/usr/bin/env bash
# Install macOS LaunchAgents: desk-up on login + optional Pro menubar.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PYTHON="$(command -v python3)"
AGENTS="${HOME}/Library/LaunchAgents"
LOG_DIR="${HOME}/.config/lemdesk"
mkdir -p "$AGENTS" "$LOG_DIR"

DESK_UP_PLIST="$AGENTS/com.lemdesk.desk-up.plist"
cat > "$DESK_UP_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.lemdesk.desk-up</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${ROOT}/bot.py</string>
    <string>lemdesk-desk-up</string>
    <string>--mount-nas</string>
    <string>--heal</string>
    <string>--mirror-nas</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/desk-up.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/desk-up.err</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/com.lemdesk.desk-up" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DESK_UP_PLIST"
echo "Installed com.lemdesk.desk-up → runs at login"
echo "  log: $LOG_DIR/desk-up.log"

if [[ "${1:-}" == "--with-pro" ]]; then
  PRO_PLIST="$AGENTS/com.lemdesk.pro.plist"
  cat > "$PRO_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.lemdesk.pro</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${ROOT}/bot.py</string>
    <string>lemdesk-pro</string>
    <string>--no-open-dashboard</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/lemdesk-pro.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/lemdesk-pro.err</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/com.lemdesk.pro" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PRO_PLIST"
  echo "Installed com.lemdesk.pro → menu bar at login"
fi

echo ""
echo "Uninstall: launchctl bootout gui/\$(id -u)/com.lemdesk.desk-up"
