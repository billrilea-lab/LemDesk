#!/usr/bin/env bash
# Run local Gordon-inspired Docker Agent supervisor (requires docker agent CLI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
YAML="${ROOT}/lemdesk/agents/lemdesk_supervisor.yaml"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 1
fi

if [[ ! -f "${YAML}" ]]; then
  echo "Missing ${YAML}"
  exit 1
fi

cd "${ROOT}"
echo "Running Docker Agent supervisor from ${YAML}"
exec docker agent run "${YAML}"
