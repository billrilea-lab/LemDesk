#!/usr/bin/env bash
# Start Open WebUI pointed at local Docker Model Runner (shared chat across LAN).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
COMPOSE="${ROOT}/lemdesk/docker-compose.open-webui.yml"
PORT="${OPEN_WEBUI_PORT:-3000}"

echo "Checking DMR on localhost:12434..."
if ! curl -sf --max-time 5 http://localhost:12434/engines/v1/models >/dev/null; then
  echo "DMR not reachable. Run: ${ROOT}/lemdesk/scripts/enable_dmr_tcp.sh"
  exit 1
fi

echo "Starting Open WebUI on port ${PORT}..."
cd "${ROOT}"
docker compose -f "${COMPOSE}" up -d

echo ""
echo "Open WebUI: http://localhost:${PORT}"
echo "LAN clients: http://<this-machine-ip>:${PORT}"
echo "In Open WebUI, select model e.g. ai/qwen2.5-coder or ai/glm-4.7-flash"
echo "Stop: docker compose -f ${COMPOSE} down"
