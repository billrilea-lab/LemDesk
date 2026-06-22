#!/usr/bin/env bash
# Launch LEMdesk Pro menu bar + dashboard
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec python3 bot.py lemdesk-pro "$@"
