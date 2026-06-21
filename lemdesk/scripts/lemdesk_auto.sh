#!/usr/bin/env bash
# Docker AI LAN — full auto pipeline (fast defaults).
# Usage:
#   ./lemdesk/scripts/lemdesk_auto.sh          # smart: extra-seeds if fresh
#   ./lemdesk/scripts/lemdesk_auto.sh --full   # full BFS scrape
#   ./lemdesk/scripts/lemdesk_auto.sh --fast   # full scrape, max speed
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
cd "${ROOT}"

EXTRA=()
if [[ "${1:-}" == "--full" ]]; then
  EXTRA+=(--full)
  shift
fi
if [[ "${1:-}" == "--fast" ]]; then
  EXTRA+=(--full --backend httpx --workers 12 --max-depth 1 --skip-dmr-check)
  shift
fi

exec python3 lemdesk_auto.py "${EXTRA[@]}" "$@"
