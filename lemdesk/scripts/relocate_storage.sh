#!/usr/bin/env bash
# Move heavy Docker/LEMdesk data off the internal SSD (Mac Mini M4).
#
# Layout:
#   /Volumes/GC-MM2/Docker/models  — DMR model weights (~15GB+)
#   /Volumes/GC-MM2/Docker         — Docker engine (Docker Desktop setting)
#   /Volumes/GC-MM2/AI-Local       — fast local cache (rag-cache, scratch)
#   /Volumes/docker/AI             — NAS shared corpus (skills, rag, backups)
#
# Usage:
#   ./lemdesk/scripts/relocate_storage.sh          # dry-run summary
#   ./lemdesk/scripts/relocate_storage.sh --apply  # move + symlink (stops Docker briefly)

set -euo pipefail

GC_MM2="/Volumes/GC-MM2"
NAS_AI="/Volumes/docker/AI"
MODELS_DST="${GC_MM2}/Docker/models"
AI_LOCAL_DST="${GC_MM2}/AI-Local"
APPLY=false
[[ "${1:-}" == "--apply" ]] && APPLY=true

say() { printf '%s\n' "$*"; }

usage_bytes() {
  if [[ -e "$1" ]]; then du -sh "$1" 2>/dev/null | awk '{print $1}'; else echo "—"; fi
}

say "=== LEMdesk storage layout ==="
say "Internal SSD (/):     $(df -h / | awk 'NR==2 {print $3 " used, " $4 " free"}')"
say "~/.docker/models:     $(usage_bytes "$HOME/.docker/models")"
say "GC-MM2 Docker:        $(usage_bytes "${GC_MM2}/Docker")"
say "GC-MM2 models target: $(usage_bytes "$MODELS_DST")"
say "NAS AI root:          $(usage_bytes "$NAS_AI")"
say ""

if [[ ! -d "$GC_MM2" ]]; then
  say "ERROR: $GC_MM2 not mounted — plug in GC-MM2 drive first."
  exit 1
fi

if [[ ! -d "$NAS_AI" ]]; then
  say "WARN: $NAS_AI not mounted — mount NAS in Finder (Cmd+K) for shared skills/RAG."
fi

link_dir() {
  local src="$1" dst="$2" label="$3"
  if [[ -L "$src" ]]; then
    say "  [ok] $label already symlink → $(readlink "$src")"
    return 0
  fi
  if [[ -d "$dst" && -d "$src" && ! -L "$src" ]]; then
    if [[ -z "$(find "$dst" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
      say "  [rm] empty existing $dst"
      rm -rf "$dst"
    else
      say "  [!!] $label: both $src and $dst exist — merge manually or empty $dst first"
      return 1
    fi
  fi
  if [[ -d "$src" && ! -L "$src" ]]; then
    if [[ -z "$(find "$src" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
      say "  [rm] empty $src"
      rm -rf "$src"
    else
      say "  [mv] $src → $dst"
      mkdir -p "$(dirname "$dst")"
      if [[ -d "$dst" ]]; then
        cp -R "$src"/. "$dst"/ 2>/dev/null || true
        rm -rf "$src"
      else
        mv "$src" "$dst"
      fi
    fi
  elif [[ ! -e "$src" ]]; then
    say "  [mkdir] $dst"
    mkdir -p "$dst"
  fi
  if [[ ! -L "$src" ]]; then
    rm -rf "$src"
    ln -s "$dst" "$src"
    say "  [link] $src → $dst"
  fi
}

if ! $APPLY; then
  say "Dry run — would:"
  say "  1. Stop Docker Desktop"
  say "  2. Move ~/.docker/models → $MODELS_DST (symlink back)"
  say "  3. Link ~/AI-Local → $AI_LOCAL_DST"
  say "  4. Ensure NAS dirs under $NAS_AI"
  say ""
  say "Docker engine root (set in Docker Desktop → Settings → Resources → Disk image):"
  docker info 2>/dev/null | grep -i "Docker Root Dir" || say "  (Docker not running)"
  say ""
  say "Re-run with --apply to execute."
  exit 0
fi

say "=== Stopping Docker Desktop ==="
docker desktop stop 2>/dev/null || true
sleep 2

say ""
say "=== Relocate DMR models to GC-MM2 ==="
mkdir -p "${GC_MM2}/Docker"
link_dir "$HOME/.docker/models" "$MODELS_DST" "DMR models"

say ""
say "=== Relocate AI-Local cache to GC-MM2 ==="
mkdir -p "$AI_LOCAL_DST/rag-cache" "$AI_LOCAL_DST/scratch"
link_dir "$HOME/AI-Local" "$AI_LOCAL_DST" "AI-Local"

say ""
say "=== Ensure NAS AI folders ==="
if [[ -d "$NAS_AI" ]]; then
  for d in skills agents rules rag backups/lemdesk lemdesk/data lemdesk/logs; do
    mkdir -p "$NAS_AI/$d"
  done
  say "  NAS AI tree OK at $NAS_AI"
fi

say ""
say "=== Starting Docker Desktop ==="
open -a Docker
for i in $(seq 1 45); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done

if docker info >/dev/null 2>&1; then
  docker desktop enable model-runner 2>/dev/null || true
  docker model ls 2>/dev/null || true
  say ""
  say "Docker OK — models at: $(readlink "$HOME/.docker/models" 2>/dev/null || echo ~/.docker/models)"
else
  say "WARN: Docker did not start — open Docker Desktop manually."
fi

say ""
say "Update ai_paths: local_fast → $AI_LOCAL_DST, synology → $NAS_AI"
say "  python3 bot.py ai-paths doctor"
