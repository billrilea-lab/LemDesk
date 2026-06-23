# Overnight build — LEMdesk Pro hardening

**Built while you slept — June 2026**

## What shipped

### 1. Login automation
- `lemdesk/scripts/install_login_item.sh` — LaunchAgent `com.lemdesk.desk-up` at login
- Optional `--with-pro` for menu bar at login
- Install: `bash lemdesk/scripts/install_login_item.sh` or `python3 bot.py lemdesk-install --login-item`

### 2. One-shot installer
- `python3 bot.py lemdesk-install` (profile: `mac-mini`)
- Does: pip, ai_paths, Docker configure, storage relocate, Cursor MCP + rules, founding license, first sync, GC backup

### 3. Cursor auto-handoff
- `.cursor/rules/lemdesk-desk.mdc` — reads handoff at every new chat
- `install_cursor.sh` + `install_cursor_rules.sh`

### 4. Pro license gate
- `lemdesk_pro/license.py` — key file + `--dev` bypass
- `python3 bot.py lemdesk-license --set|--status`
- Menubar requires license unless `--dev`

### 5. Self-healing desk
- `lemdesk-desk-up --heal` — relocate models, auto-sync if stale
- `--mirror-nas` — copy corpus to NAS after up
- NAS path auto-detect (`discover_nas_ai`) — finds `/Volumes/docker/AI` vs `docker-1`

### 6. Stability
- Menu bar single-instance lock (`instance_lock.py`)
- Dashboard port reuse if already running
- No browser spam on relaunch (`--no-open-dashboard`)

### 7. NAS canonical mirror
- `lemdesk/nas_mirror.py` — sync data/logs/skills to NAS on each `lemdesk-sync`

## Your morning commands

```bash
cd "/Users/williamrilea/Cursor- Crypto"

# If login agent not installed yet:
bash lemdesk/scripts/install_login_item.sh --with-pro

# Or one-shot:
python3 bot.py lemdesk-desk-up --heal --mount-nas --mirror-nas
python3 bot.py lemdesk-pro

# License check:
python3 bot.py lemdesk-license --status
```

## Files added/changed

| File | Purpose |
|------|---------|
| `lemdesk_pro/license.py` | Pro license |
| `lemdesk_pro/instance_lock.py` | Single menubar instance |
| `lemdesk_pro/desk_up.py` | Heal + NAS mirror |
| `lemdesk/nas_mirror.py` | NAS sync |
| `lemdesk/path_registry.py` | NAS auto-detect |
| `.cursor/rules/lemdesk-desk.mdc` | Auto-handoff rule |
| `lemdesk/scripts/lemdesk_install.sh` | Full installer |
| `lemdesk/scripts/install_login_item.sh` | LaunchAgents |
| `lemdesk/scripts/install_cursor*.sh` | MCP + rules |
| `lemdesk/PRO_COMMERCE.md` | Stripe guide |
| `lemdesk/LEMdesk_SYSTEM_REPORT.md` | NotebookLM source |

## Still manual (Stripe)

1. Create Stripe $19/mo Payment Link
2. Paste link in lemdev.com pricing page
3. Email keys to founding members

See `lemdesk/PRO_COMMERCE.md`.

## Product status

**Working product:** YES for personal + demo use  
**Commercial:** License gate in place; Stripe link is your step  
**Desk Health target:** 100/100 after `desk-up --heal`

Good morning.
