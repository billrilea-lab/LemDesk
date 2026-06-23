#!/usr/bin/env bash
# Install Cursor rules for LEMdesk desk continuity.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
SRC="$ROOT/.cursor/rules/lemdesk-desk.mdc"
DEST_DIR="${HOME}/.cursor/rules"
DEST="$DEST_DIR/lemdesk-desk.mdc"

mkdir -p "$DEST_DIR"
if [[ -f "$SRC" ]]; then
  cp "$SRC" "$DEST"
  echo "Installed Cursor rule → $DEST"
else
  echo "WARN: missing $SRC"
fi

# Personal skills
for skill in lemdesk docker-mac-storage; do
  if [[ -d "$ROOT/.cursor/skills/$skill" ]]; then
    mkdir -p "${HOME}/.cursor/skills/$skill"
    cp "$ROOT/.cursor/skills/$skill/SKILL.md" "${HOME}/.cursor/skills/$skill/SKILL.md"
    echo "  skill: $skill"
  fi
done
