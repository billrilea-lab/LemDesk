---
name: docker-mac-storage
description: >-
  Mac Mini / small-SSD Docker Desktop storage — relocate DMR models and engine
  off the internal drive to GC-MM2 USB SSD or NAS. Use when Docker fills the
  disk, models are slow to find, DMR models missing after reboot, NAS mount path
  drift (docker vs docker-1), or user asks where Docker data should live on
  Mac-Mini-2 with LEMdesk.
---

# Docker + storage on Mac Mini (small internal SSD)

**Machine:** Mac-Mini-2 · **Cursor** is primary AI IDE · **LEMdesk** manages paths.

## Storage map (do not put heavy data on `/`)

| What | Where | Why |
|------|-------|-----|
| Docker engine | `/Volumes/GC-MM2/Docker` | Set in Docker Desktop → Settings → Resources → Disk image |
| DMR model weights (~15GB+) | `~/.docker/models` → **symlink** → `/Volumes/GC-MM2/Docker/models` | Models default to internal SSD; symlink is the fix |
| Fast cache | `~/AI-Local` → `/Volumes/GC-MM2/AI-Local` | rag-cache, scratch |
| Shared AI corpus | `/Volumes/docker/AI` (NAS SMB) | skills, rag, rules, backups — **not** `/Volumes/docker-1` |

**NAS mount:** Finder Cmd+K → `smb://DiskRack1SDR._smb._tcp.local/docker` → mounts as `/Volumes/docker` (name may vary; check `ls /Volumes`).

## Morning checklist (disk full / DMR empty / paths 76)

```bash
ls /Volumes/GC-MM2 /Volumes/docker/AI    # both mounted?
open -a Docker
docker info | grep "Docker Root Dir"     # expect GC-MM2/Docker
ls -la ~/.docker/models                  # expect symlink → GC-MM2
docker desktop enable model-runner
docker model ls
python3 bot.py ai-paths doctor
```

## One-shot fix (repo)

```bash
cd "/Users/williamrilea/Cursor- Crypto"
./lemdesk/scripts/relocate_storage.sh          # dry-run
./lemdesk/scripts/relocate_storage.sh --apply  # stop Docker, move models, symlink
./lemdesk/scripts/configure_docker_desktop.sh
```

## Manual model relocate (if script not available)

```bash
docker desktop stop
mv ~/.docker/models /Volumes/GC-MM2/Docker/models   # if GC-MM2/Docker/models empty
ln -s /Volumes/GC-MM2/Docker/models ~/.docker/models
open -a Docker
docker model ls
```

**Nested folder bug:** If `mv` lands in existing `GC-MM2/Docker/models/`, blobs end up at `models/models/blobs`. Flatten:

```bash
docker desktop stop
DST=/Volumes/GC-MM2/Docker/models
mv "$DST/models/"{blobs,bundles,manifests,layout.json,models.json} "$DST/"
rm -rf "$DST/models"
open -a Docker && docker model ls
```

## AI paths config

File: `~/.config/lemdesk/ai_paths.yaml`

```yaml
volumes:
  synology:
    mac: /Volumes/docker/AI
machines:
  Mac-Mini-2:
    volumes:
      synology: /Volumes/docker/AI
      local_fast: /Volumes/GC-MM2/AI-Local
```

Verify: `python3 bot.py ai-paths doctor` → **100/100**

## DMR / Cursor

| Setting | Value |
|---------|--------|
| Base URL | `http://localhost:12434/engines/v1` |
| API key | `not-needed` |
| Models | `docker.io/ai/smollm2:latest`, `docker.io/ai/devstral-small-2:latest` |

Enable TCP if needed: `docker desktop enable model-runner` (GUI: Settings → AI → Model Runner + host TCP :12434).

## What stays on internal SSD

- macOS, Cursor app, monorepo code (`~/Cursor- Crypto`)
- `~/.cursor/` config (small)
- **Not** 15GB model blobs

## Related

- `lemdesk/scripts/relocate_storage.sh`
- `lemdesk/scripts/configure_docker_desktop.sh`
- `lemdesk/AI_PATHS.md`
- `.cursor/skills/lemdesk/SKILL.md`
