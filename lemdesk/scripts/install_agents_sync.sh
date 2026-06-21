#!/usr/bin/env bash
# Install agents_sync for cross-tool agent/skill/MCP sync (optional).
set -euo pipefail

echo "agents_sync — sync ~/.cursor agents, skills, rules, commands, mcp.json"
echo "across Cursor, Claude, Gemini, Antigravity, Codex, Copilot."
echo ""
echo "Repo: https://github.com/CognitiveSand/agents_sync"
echo ""
echo "Also sync from this repo:"
echo "  lemdesk/agents/  (Docker Agent YAML)"
echo "  .cursor/skills/        (project skills)"
echo ""
echo "Paths template: lemdesk/scripts/cursor_sync_paths.json"
echo ""

if ! command -v git >/dev/null 2>&1; then
  echo "git required to clone agents_sync"
  exit 1
fi

TARGET="${HOME}/agents_sync"
if [[ -d "${TARGET}" ]]; then
  echo "Already exists: ${TARGET}"
  echo "Run: cd ${TARGET} && git pull && see README for daemon setup"
  exit 0
fi

read -r -p "Clone agents_sync to ${TARGET}? [y/N] " ans
if [[ "${ans}" != "y" && "${ans}" != "Y" ]]; then
  echo "Skipped. Manual: git clone https://github.com/CognitiveSand/agents_sync ${TARGET}"
  exit 0
fi

git clone https://github.com/CognitiveSand/agents_sync "${TARGET}"
echo ""
echo "Next: follow ${TARGET}/README.md to start the sync daemon."
echo "Include lemdesk/agents in your sync paths or copy YAML to ~/.cursor/agents/"
