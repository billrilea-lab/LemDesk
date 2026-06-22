# LEMdesk — Local Setup Guide

Complete setup for **Starter** (free sample) + **Pro** (menu bar, Smart Handoff, dashboard) with **Docker Desktop Model Runner** and **Cursor**.

Website: [lemdev.com](https://lemdev.com) · Repo: [github.com/billrilea-lab/LemDesk](https://github.com/billrilea-lab/LemDesk)

---

## What you're building

| Layer | Purpose |
|-------|---------|
| **Docker Model Runner** | One local model API on your LAN (`:12434`) |
| **LEMdesk Starter** | Knowledge sync, RAG, MCP, session handoff |
| **LEMdesk Pro** | Menu bar health, Smart Handoff desk packs, dashboard `:8765` |
| **Cursor** | Local model + LEMdesk MCP tools |

**The problem LEMdesk solves:** Cursor doesn't sync across rooms. LEMdesk wires model URL, docs, and agent context on your LAN.

---

## 1. Prerequisites

- macOS (menu bar Pro) or Linux/Windows (CLI Pro dashboard)
- Python 3.10+
- Docker Desktop 4.40+ with **Model Runner** enabled
- Cursor IDE

```bash
git clone https://github.com/billrilea-lab/LemDesk.git
cd LemDesk
pip install -r requirements.txt
# macOS menu bar:
pip install rumps
```

---

## 2. Configure Docker Desktop

One-shot script (fixes CLI plugins, enables TCP, probes DMR):

```bash
./lemdesk/scripts/configure_docker_desktop.sh
```

Or manually:

```bash
# Fix broken plugin symlinks after reinstall
PLUGIN_DIR="$HOME/.docker/cli-plugins"
APP="/Applications/Docker.app/Contents/Resources/cli-plugins"
for p in docker-model docker-desktop docker-mcp docker-agent; do
  ln -sf "$APP/$p" "$PLUGIN_DIR/$p"
done

# Enable Model Runner TCP (LEMdesk default port)
docker desktop enable model-runner --tcp=12434 --cors=all

# Verify
./lemdesk/scripts/check_dmr.sh
```

**Docker Desktop UI:** Settings → **AI** → enable **Docker Model Runner** + **host-side TCP** on port `12434`.

Pull a model:

```bash
docker model pull ai/smollm2          # small, fast test
docker model pull ai/devstral-small-2 # better for coding
docker model ls
```

---

## 3. Wire Cursor to local models

**Cursor → Settings → Models → OpenAI-compatible**

| Field | Value |
|-------|--------|
| Base URL | `http://localhost:12434/engines/v1` |
| API key | `not-needed` |
| Model | `docker.io/ai/smollm2:latest` (or your pulled model) |

**Other machines on LAN:** `http://<server-ip>:12434/engines/v1`  
(Find IP: `ipconfig getifaddr en0` on Mac)

---

## 4. LEMdesk Starter — sync the desk

```bash
python3 lemdesk_auto.py --fast --skip-dmr-check
# or: python3 bot.py lemdesk-sync --fast --skip-dmr-check
```

This rebuilds knowledge corpus, RAG index, runbooks, and session handoff.

---

## 5. LEMdesk Pro — menu bar + dashboard

```bash
python3 -m lemdesk_pro menubar
# or: python3 bot.py lemdesk-pro
# headless dashboard only:
python3 -m lemdesk_pro menubar --cli
```

| URL | What |
|-----|------|
| http://127.0.0.1:8765/ | Desk Health dashboard |
| http://127.0.0.1:8765/health | JSON API |
| http://127.0.0.1:8765/desk-pack | Smart Handoff JSON |

**Menu bar actions:** Open Dashboard · Desk Health · Sync Now · Smart Handoff (copies prompt to clipboard)

---

## 6. Cursor MCP — local knowledge search

Copy `lemdesk/mcp/cursor_mcp.json.example` to `~/.cursor/mcp.json` and set the full path to `lemdesk_mcp_server.py`:

```json
{
  "mcpServers": {
    "lemdesk-kb": {
      "command": "python3",
      "args": ["/full/path/to/LemDesk/lemdesk_mcp_server.py"],
      "env": {}
    }
  }
}
```

Reload Cursor (`Cmd+Shift+P` → Reload Window).

**Tools:** `search_lemdesk_docs` · `get_lemdesk_handoff` · `get_lemdesk_setup_facts` · `list_lemdesk_topics`

---

## 7. Smart Handoff (cross-room continuity)

Before switching desks:

```bash
python3 -m lemdesk_pro smart-handoff --focus "what you were building"
# → lemdesk/logs/desk_handoff_prompt.md
```

Paste the prompt into Cursor in your other room. Pro menu bar: **Smart Handoff** copies to clipboard automatically.

---

## 8. Desk Health score

```bash
python3 -m lemdesk_pro health
# or: python3 bot.py lemdesk-health --json
```

| Score | Meaning |
|-------|---------|
| 85+ (A) | Production-ready — DMR, RAG, MCP, handoff green |
| 65+ (B) | Healthy — quick sync helps |
| &lt;40 (D) | Run sync + configure Docker |

Checks: DMR · knowledge corpus · RAG · handoff · MCP · agent sync inbox

---

## 9. Demo for friends (60 seconds)

1. `./lemdesk/scripts/configure_docker_desktop.sh`
2. `python3 lemdesk_auto.py --fast --skip-dmr-check`
3. `python3 -m lemdesk_pro menubar` → show menu bar score
4. Open http://127.0.0.1:8765 → live dashboard
5. Smart Handoff → paste into Cursor
6. [lemdev.com/demo.html](https://lemdev.com/demo.html) detects live Pro desk

**Pitch:** *"Cursor doesn't follow you between rooms. I wired my LAN — one model, one doc corpus, one agent thread everywhere."*

---

## 10. Troubleshooting

| Issue | Fix |
|-------|-----|
| `docker model` unknown | Re-link CLI plugins (see §2) |
| DMR unreachable on `:12434` | `docker desktop enable model-runner --tcp=12434` |
| Stale install path | Fix `DockerAppLaunchPath` in `~/Library/Group Containers/group.com.docker/settings-store.json` → `/Applications/Docker.app` |
| Low health score | Run sync; start Docker; pull a model |
| MCP tools missing | Check `~/.cursor/mcp.json` path; reload Cursor |

---

## Links

- [lemdev.com](https://lemdev.com) — product site
- [Pricing / Pro waitlist](https://lemdev.com/pricing.html)
- [Live demo walkthrough](https://lemdev.com/demo.html)
- [lemdesk/README.md](README.md) — component reference

MIT · Independent project · Not affiliated with Docker, Cursor, Anthropic, or OpenAI.
