#!/usr/bin/env bash
# Detect LAN IP and probe DMR on localhost + suggest LAN client URL.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PORT="${DMR_PORT:-12434}"
BASE_LOCAL="http://localhost:${PORT}"

echo "=== Docker Model Runner check ==="
if command -v docker >/dev/null 2>&1; then
  docker model status 2>&1 || echo "(docker model status failed — is DMR enabled?)"
else
  echo "docker CLI not found"
fi

echo ""
echo "=== Local probe ${BASE_LOCAL}/engines/v1/models ==="
if curl -sf --max-time 10 "${BASE_LOCAL}/engines/v1/models" | head -c 500; then
  echo ""
  echo "OK: localhost endpoint responding"
else
  echo "FAIL: cannot reach ${BASE_LOCAL}/engines/v1/models"
  echo "Enable: Docker Desktop > Settings > AI > Model Runner + host-side TCP"
  echo "Or: ./lemdesk/scripts/enable_dmr_tcp.sh"
fi

echo ""
echo "=== LAN addresses (for thin clients) ==="
LAN_IP=""
if command -v ipconfig >/dev/null 2>&1; then
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
fi
if [[ -z "${LAN_IP}" ]] && command -v hostname >/dev/null 2>&1; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
fi
if [[ -n "${LAN_IP}" ]]; then
  echo "Suggested Cursor base URL for other machines:"
  echo "  http://${LAN_IP}:${PORT}/engines/v1"
  echo ""
  echo "LAN probe (may fail if firewall blocks non-localhost):"
  curl -sf --max-time 5 "http://${LAN_IP}:${PORT}/engines/v1/models" | head -c 200 && echo "" || \
    echo "  (LAN bind not reachable — check firewall / Docker TCP bind settings)"
else
  echo "Could not detect LAN IP. Use: http://<server-ip>:${PORT}/engines/v1"
fi

echo ""
echo "Docs: ${ROOT}/lemdesk/logs/lemdesk_agent_context.md"
echo "Security: only expose ${PORT} on trusted LAN; use firewall rules."
