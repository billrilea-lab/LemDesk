# AI Paths — one map for skills, agents, RAG, Synology, Mac & Windows

**The pain:** `~/.cursor/skills` on Mac, `Z:\AI\skills` on Windows, Synology at `/Volumes/Synology/AI` — agents break when paths differ.

**The fix:** One YAML registry of **logical names** → **physical paths per machine**. An assistant resolves them and tells you what's missing.

---

## Quick start

```bash
python3 -m pip install pyyaml
python3 bot.py ai-paths init          # copy template → ~/.config/lemdesk/ai_paths.yaml
python3 bot.py ai-paths wizard        # interactive: Synology + local paths
python3 bot.py ai-paths doctor        # what exists / what's missing
python3 bot.py ai-paths repair       # fix bad wizard paste / corrupt yaml
python3 bot.py ai-paths resolve rag   # print resolved path
python3 bot.py ai-paths brief         # ai_path_map.md for Cursor
```

Or directly:

```bash
python3 lemdesk/scripts/ai_path_assistant.py wizard
```

---

## Config locations

| Priority | Path |
|----------|------|
| 1 | `$LEMDESK_AI_PATHS` (env override) |
| 2 | `~/.config/lemdesk/ai_paths.yaml` (Mac/Linux) |
| 3 | `%APPDATA%/lemdesk/ai_paths.yaml` (Windows) |
| 4 | `lemdesk/config/ai_paths.yaml` (project) |
| 5 | `lemdesk/config/ai_paths.template.yaml` (defaults) |

---

## Logical paths (built-in)

| Name | Typical use |
|------|-------------|
| `skills` | `.cursor/skills` or NAS mirror |
| `agents` | `.cursor/agents` |
| `rules` | `.cursor/rules` |
| `mcp` | `~/.cursor/mcp.json` |
| `rag` | Master RAG corpus (Synology) |
| `rag_cache` | Local fast cache |
| `knowledge` | `knowledge.json` |
| `data` | LEMdesk data dir |
| `logs` | Handoff + desk packs |
| `secrets` | `secrets.env` (never git) |
| `backups` | Tarball destination |
| `projects` | Code workspaces root |

---

## Mac Mini storage layout (small internal SSD)

Keep the **228GB internal drive** for macOS + apps only. Heavy data goes external:

| What | Where | Size |
|------|-------|------|
| Docker engine | `/Volumes/GC-MM2/Docker` | Docker Desktop → Settings → Resources |
| DMR model weights | `~/.docker/models` → symlink to `/Volumes/GC-MM2/Docker/models` | ~15GB+ |
| Fast cache | `~/AI-Local` → `/Volumes/GC-MM2/AI-Local` | rag-cache, scratch |
| Shared AI corpus | `/Volumes/docker/AI` (NAS) | skills, rag, backups |

One-shot relocate (stops Docker briefly):

```bash
./lemdesk/scripts/relocate_storage.sh --apply
```

---

**Mac** (`Mac-Mini-2`):
```yaml
machines:
  Mac-Mini-2:
    volumes:
      synology: /Volumes/docker/AI
      local_fast: /Volumes/GC-MM2/AI-Local
```

**Windows** (`WIN-PC`):
```yaml
machines:
  WIN-PC:
    volumes:
      synology: "Z:/AI"
```

Mount Synology in Finder (Mac) or map network drive (Windows) **before** running doctor.

---

## Shell exports

```bash
python3 bot.py ai-paths export --out ~/.lemdesk_paths.sh
source ~/.lemdesk_paths.sh
echo $LEMDESK_SKILLS
```

Add to `~/.zshrc` or Windows PowerShell profile.

---

## Cursor MCP tools

After reload, ask the agent:

- `resolve_ai_path("rag")`
- `ai_path_doctor()`

---

## Path tokens in YAML

| Token | Expands to |
|-------|------------|
| `{home}` | User home |
| `{project}` | Repo root |
| `{volume:synology}` | This machine's Synology mount |
| `{volume:local_fast}` | Local SSD cache |

First existing candidate wins (or set `primary:` index).

---

## Windows notes

- Use forward slashes: `Z:/AI/skills`
- Or `%USERNAME%` in paths
- Run wizard from PowerShell or Git Bash

---

See also: [SETUP.md](SETUP.md)
