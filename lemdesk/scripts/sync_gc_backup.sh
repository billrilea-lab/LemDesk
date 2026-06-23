#!/usr/bin/env bash
# Mirror LEMdesk Pro to GC-MM2 local backup (offline copy on external SSD).
# Default: /Volumes/GC-MM2/lemdev.com/LemDesk/Pro
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
DEST="${LEMdesk_GC_BACKUP:-/Volumes/GC-MM2/lemdev.com/LemDesk/Pro}"

if [[ ! -d /Volumes/GC-MM2 ]]; then
  echo "ERROR: GC-MM2 not mounted at /Volumes/GC-MM2"
  exit 1
fi

mkdir -p "$DEST"

copy() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$DEST/$dst")"
  rsync -a --delete "$ROOT/$src" "$DEST/$dst"
}

echo "=== LEMdesk GC-MM2 backup → $DEST ==="

for item in lemdesk_pro lemdesk lemdesk_auto.py lemdesk_brief.py lemdesk_mcp_server.py scrape_lemdesk.py requirements.txt bot.py; do
  if [[ -e "$ROOT/$item" ]]; then
    if [[ -d "$ROOT/$item" ]]; then
      rsync -a --delete \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude 'incoming/*.json' \
        --exclude 'data/rag_bm25.db' \
        --exclude 'data/raw' \
        "$ROOT/$item/" "$DEST/$item/"
    else
      cp "$ROOT/$item" "$DEST/$item"
    fi
    echo "  synced $item"
  fi
done

if [[ -d "$ROOT/.cursor/skills/lemdesk" ]]; then
  mkdir -p "$DEST/.cursor/skills"
  rsync -a "$ROOT/.cursor/skills/lemdesk/" "$DEST/.cursor/skills/lemdesk/"
  echo "  synced .cursor/skills/lemdesk"
fi
if [[ -d "$ROOT/.cursor/skills/docker-mac-storage" ]]; then
  rsync -a "$ROOT/.cursor/skills/docker-mac-storage/" "$DEST/.cursor/skills/docker-mac-storage/"
  echo "  synced .cursor/skills/docker-mac-storage"
fi

cat > "$DEST/README.md" <<EOF
# LEMdesk Pro — GC-MM2 local backup

Offline mirror on external SSD. **Canonical repo:** [github.com/billrilea-lab/LemDesk](https://github.com/billrilea-lab/LemDesk)

**Synced:** $(date -u +"%Y-%m-%d %H:%M UTC")
**Source:** $ROOT

## Quick start from this copy

\`\`\`bash
cd "$DEST"
pip install -r requirements.txt
python3 bot.py lemdesk-desk-up
python3 bot.py lemdesk-pro
\`\`\`

Refresh backup from Mac monorepo:

\`\`\`bash
./lemdesk/scripts/sync_gc_backup.sh
\`\`\`
EOF

echo "Done → $DEST"
