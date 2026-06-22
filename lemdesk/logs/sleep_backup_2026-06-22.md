# Sleep backup — 2026-06-22

> Local snapshot before sleep. Pick up via `session_handoff.md` or paste `desk_handoff_prompt.md` into a new Cursor room.

## Scores

| Check | Score | Notes |
|-------|-------|-------|
| AI Path Health | **100/100** | Fixed: `mkdir -p ~/.cursor/commands` |
| Desk Health | **95/100 (A)** | Optional: `python3 bot.py lemdesk-sync --fast` clears 56 inbox files |

## What we built tonight

- **LEMdesk Pro** — `lemdesk_pro/` desk health, smart handoff, menu bar + dashboard `:8765`
- **AI Path Registry** — `lemdesk/path_registry.py`, wizard/doctor/repair, `~/.config/lemdesk/ai_paths.yaml`
- **CLI** — `python3 bot.py lemdesk-pro|lemdesk-health|lemdesk-smart-handoff|ai-paths {wizard|doctor|repair|brief}`
- **lemdev.com** — pricing, demo, Starter vs Pro pages (repo: `billrilea-lab/lemdev.com`)
- **LemDesk GitHub** — `billrilea-lab/LemDesk` via `.lemdesk-push/`

## Key paths (Mac-Mini-2)

| Logical | Resolved |
|---------|----------|
| NAS AI root | `/Volumes/docker-1/AI` |
| skills / rag / rules | `/Volumes/docker-1/AI/{skills,rag,rules}` |
| backups | `/Volumes/docker-1/AI/backups/lemdesk` |
| secrets | `~/.config/cursor-crypto/secrets.env` |
| MCP | `~/.cursor/mcp.json` |
| commands | `~/.cursor/commands` |
| monorepo | `/Users/williamrilea/Cursor- Crypto` |

## Docker / DMR

- Docker Desktop 4.68+ running
- Model Runner TCP `:12434` enabled
- Models: `smollm2`, `devstral-small-2`
- Check: `./lemdesk/scripts/check_dmr.sh`

## Git remotes

| Repo | Remote |
|------|--------|
| Monorepo (`Cursor- Crypto`) | local only — no origin |
| LemDesk | `git@github.com:billrilea-lab/LemDesk.git` → `.lemdesk-push/` |
| lemdev.com | `git@github.com:billrilea-lab/lemdev.com.git` → `lemdev-site/` |

## Pick up tomorrow

1. Read `lemdesk/logs/session_handoff.md`
2. `python3 bot.py lemdesk-health` and `python3 bot.py ai-paths doctor`
3. Optional inbox: `python3 bot.py lemdesk-sync --fast`
4. Windows profile in `ai_paths.yaml` if setting up WIN-PC
5. GoDaddy DNS for lemdev.com if not live yet

## Commands cheat sheet

```bash
cd "/Users/williamrilea/Cursor- Crypto"
python3 bot.py lemdesk-health
python3 bot.py ai-paths doctor
python3 bot.py lemdesk-handoff --read
python3 -m lemdesk_pro menubar          # menu bar app
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
cd .lemdesk-push && git push origin main
```

---
*Generated before sleep — LEMdesk session backup.*
