#!/usr/bin/env bash
# Install weekly launchd job for Docker AI auto-refresh (macOS).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PLIST_NAME="com.cursor-crypto.lemdesk-auto"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="${ROOT}/lemdesk/logs"
AUTO_SH="${ROOT}/lemdesk/scripts/lemdesk_auto.sh"

mkdir -p "${LOG_DIR}"

cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_NAME}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${AUTO_SH}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>15</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/auto_cron.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/auto_cron.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${PLIST_NAME}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"

echo "Installed weekly auto job (Monday 03:15): ${PLIST_PATH}"
echo "Logs: ${LOG_DIR}/auto_cron.log"
echo "Uninstall: launchctl bootout gui/$(id -u)/${PLIST_NAME} && rm ${PLIST_PATH}"
