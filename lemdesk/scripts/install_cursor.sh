#!/usr/bin/env bash
# Wire LEMdesk MCP into ~/.cursor/mcp.json (merge, do not wipe).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
MCP_SERVER="$ROOT/lemdesk_mcp_server.py"
CURSOR_MCP="${HOME}/.cursor/mcp.json"

if [[ ! -f "$MCP_SERVER" ]]; then
  echo "ERROR: $MCP_SERVER not found"
  exit 1
fi

python3 - "$CURSOR_MCP" "$MCP_SERVER" <<'PY'
import json, sys
from pathlib import Path

mcp_path = Path(sys.argv[1])
server = sys.argv[2]
entry = {
    "command": "python3",
    "args": [server],
    "env": {},
}
data = {}
if mcp_path.exists():
    try:
        data = json.loads(mcp_path.read_text())
    except json.JSONDecodeError:
        data = {}
servers = data.setdefault("mcpServers", {})
servers["lemdesk-kb"] = entry
mcp_path.parent.mkdir(parents=True, exist_ok=True)
mcp_path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {mcp_path}")
print(f"  lemdesk-kb → {server}")
PY

echo "Reload Cursor (Cmd+Shift+P → Reload Window) to activate MCP."
