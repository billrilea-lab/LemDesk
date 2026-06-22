#!/usr/bin/env bash
# Configure Docker Desktop for LEMdesk: Model Runner TCP, CLI plugins, DMR probe.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PORT="${DMR_PORT:-12434}"
APP_PLUGINS="/Applications/Docker.app/Contents/Resources/cli-plugins"
PLUGIN_DIR="${HOME}/.docker/cli-plugins"
SETTINGS="${HOME}/Library/Group Containers/group.com.docker/settings-store.json"

echo "=== LEMdesk — Docker Desktop configure ==="

if [[ ! -d /Applications/Docker.app ]]; then
  echo "ERROR: Docker Desktop not found at /Applications/Docker.app"
  echo "Install from https://www.docker.com/products/docker-desktop/"
  exit 1
fi

echo ""
echo "=== Fix CLI plugin symlinks ==="
mkdir -p "$PLUGIN_DIR"
for p in docker-model docker-desktop docker-mcp docker-agent docker-ai; do
  if [[ -f "$APP_PLUGINS/$p" ]]; then
    ln -sf "$APP_PLUGINS/$p" "$PLUGIN_DIR/$p"
    echo "  linked $p"
  fi
done

if [[ -f "$SETTINGS" ]] && grep -q "in_progress/Docker.app" "$SETTINGS" 2>/dev/null; then
  echo ""
  echo "=== Fix stale DockerAppLaunchPath in settings ==="
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$SETTINGS" <<'PY'
import json, sys
path = sys.argv[1]
data = json.loads(open(path).read())
old = data.get("DockerAppLaunchPath", "")
if "in_progress" in old:
    data["DockerAppLaunchPath"] = "/Applications/Docker.app"
    data["EnableDockerAI"] = True
    data["EnableInferenceTCP"] = True
    open(path, "w").write(json.dumps(data, indent=2) + "\n")
    print("  updated settings-store.json")
PY
  fi
fi

echo ""
echo "=== Ensure Docker engine is up ==="
if ! docker info >/dev/null 2>&1; then
  echo "Starting Docker Desktop..."
  open -a Docker
  for i in $(seq 1 60); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi
docker info >/dev/null 2>&1 || { echo "ERROR: Docker daemon not responding"; exit 1; }
echo "  Docker engine OK"

echo ""
echo "=== Enable Model Runner TCP on :${PORT} ==="
docker desktop enable model-runner --tcp="${PORT}" --cors=all 2>&1 || \
  docker desktop enable model-runner --tcp="${PORT}" 2>&1

echo ""
echo "=== Model status ==="
docker model status 2>&1 || true
docker model ls 2>&1 || true

echo ""
echo "=== DMR probe ==="
"$(dirname "$0")/check_dmr.sh"

echo ""
echo "=== Cursor settings (manual) ==="
echo "  Base URL: http://localhost:${PORT}/engines/v1"
echo "  API key:  not-needed"
echo "  Model:    docker.io/ai/smollm2:latest  (or pull ai/qwen2.5-coder)"
echo ""
echo "Pull a coder model:"
echo "  docker model pull ai/qwen2.5-coder"
echo ""
echo "LEMdesk health:"
echo "  cd \"$ROOT\" && python3 bot.py lemdesk-health"
