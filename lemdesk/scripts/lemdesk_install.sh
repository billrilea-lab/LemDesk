#!/usr/bin/env bash
# LEMdesk one-shot installer — profiles: mac-mini | default
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PROFILE="${1:-mac-mini}"
SCRIPTS="$ROOT/lemdesk/scripts"

say() { printf '%s\n' "$*"; }

say "=== LEMdesk Install (profile: $PROFILE) ==="
say "Root: $ROOT"

# 1. Python deps
say ""
say "=== Python dependencies ==="
python3 -m pip install -q -r "$ROOT/requirements.txt"
if [[ "$(uname)" == "Darwin" ]]; then
  python3 -m pip install -q rumps 2>/dev/null || true
fi

# 2. AI paths
say ""
say "=== AI path registry ==="
python3 "$ROOT/bot.py" ai-paths init 2>/dev/null || true
if [[ "$PROFILE" == "mac-mini" ]]; then
  python3 - "$HOME/.config/lemdesk/ai_paths.yaml" <<'PY'
import yaml, socket
from pathlib import Path
p = Path.home() / ".config/lemdesk/ai_paths.yaml"
data = yaml.safe_load(p.read_text()) if p.exists() else {}
host = socket.gethostname().split(".")[0]
data.setdefault("volumes", {}).setdefault("synology", {})["mac"] = "/Volumes/docker/AI"
data.setdefault("volumes", {}).setdefault("local_fast", {})["mac"] = "/Volumes/GC-MM2/AI-Local"
data.setdefault("volumes", {}).setdefault("gc_backup", {})["mac"] = "/Volumes/GC-MM2/lemdev.com/LemDesk/Pro"
machines = data.setdefault("machines", {})
prof = machines.setdefault(host, {"os": "darwin", "volumes": {}})
prof["volumes"] = {
    "synology": "/Volumes/docker/AI",
    "local_fast": "/Volumes/GC-MM2/AI-Local",
    "gc_backup": "/Volumes/GC-MM2/lemdev.com/LemDesk/Pro",
}
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
print(f"  wrote {p} for {host}")
PY
fi

# 3. Docker (non-fatal if not installed)
say ""
say "=== Docker Model Runner ==="
if command -v docker >/dev/null 2>&1; then
  bash "$SCRIPTS/configure_docker_desktop.sh" || say "  (configure had warnings — check Docker Desktop UI)"
else
  say "  Docker not found — install Docker Desktop, then re-run desk-up"
fi

# 4. Storage relocate (mac-mini)
if [[ "$PROFILE" == "mac-mini" ]] && [[ -d /Volumes/GC-MM2 ]]; then
  say ""
  say "=== Storage (GC-MM2) ==="
  bash "$SCRIPTS/relocate_storage.sh" --apply 2>/dev/null || say "  relocate skipped or partial"
fi

# 5. Cursor
say ""
say "=== Cursor MCP + rules ==="
bash "$SCRIPTS/install_cursor.sh"
bash "$SCRIPTS/install_cursor_rules.sh"

# 6. Founding license for this machine
say ""
say "=== Pro license (founding) ==="
KEY=$(python3 -c "import sys; sys.path.insert(0, '$ROOT'); from lemdesk_pro.license import generate_machine_key; print(generate_machine_key())")
mkdir -p "$HOME/.config/lemdesk"
echo "$KEY" > "$HOME/.config/lemdesk/license.key"
chmod 600 "$HOME/.config/lemdesk/license.key"
say "  License: $KEY"

# 7. First desk-up + sync
say ""
say "=== First desk-up + sync ==="
cd "$ROOT"
python3 bot.py lemdesk-desk-up --mount-nas --heal || true
python3 bot.py lemdesk-sync --fast --skip-dmr-check 2>/dev/null || say "  sync skipped"

# 8. GC backup mirror
if [[ -d /Volumes/GC-MM2/lemdev.com/LemDesk/Pro ]]; then
  bash "$SCRIPTS/sync_gc_backup.sh" 2>/dev/null || true
fi

say ""
say "=== Install complete ==="
say "  python3 bot.py lemdesk-desk-up --heal"
say "  python3 bot.py lemdesk-pro"
say "  Dashboard: http://127.0.0.1:8765"
say ""
say "Optional login items:"
say "  bash $SCRIPTS/install_login_item.sh"
