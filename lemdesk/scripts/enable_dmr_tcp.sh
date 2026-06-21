#!/usr/bin/env bash
# Enable Docker Model Runner with host TCP (macOS Docker Desktop).
set -euo pipefail
PORT="${DMR_PORT:-12434}"

echo "Enabling Model Runner TCP on port ${PORT}..."
if docker desktop enable model-runner --tcp "${PORT}" 2>&1; then
  echo "Done."
else
  echo "CLI failed — enable manually:"
  echo "  Docker Desktop > Settings > AI > Enable Docker Model Runner"
  echo "  Enable host-side TCP support, port ${PORT}"
fi

echo ""
echo "Optional: add CORS origins for browser tools in Settings > AI > CORS Allowed Origins"
echo "Verify: $(dirname "$0")/check_dmr.sh"
