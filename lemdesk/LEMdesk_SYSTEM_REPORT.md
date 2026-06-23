# LEMdesk System Report — Product, Architecture, Installation & Operations

**Document purpose:** Upload this file to Google NotebookLM to generate audio overviews, study guides, or Q&A about the LEMdesk system.  
**Author:** LEMdev · **Date:** June 2026 · **Version:** Pro 0.1.0-demo  
**Live site:** [lemdev.com](https://lemdev.com) · **Open source:** [github.com/billrilea-lab/LemDesk](https://github.com/billrilea-lab/LemDesk)

---

## 1. Executive summary — Is this a working product?

**Yes — as a local developer desk kit and demo-ready Pro app.**  
**Not yet — as a paid SaaS with billing and license enforcement.**

| Edition | Status | Who it's for |
|---------|--------|--------------|
| **LEMdesk Starter** (free, MIT) | **Shipping** — clone, install, sync, MCP, handoff | Developers proving local AI desk sync on their LAN |
| **LEMdesk Pro** ($19/mo planned) | **Working demo build** — menu bar, health score, dashboard, Smart Handoff | Daily driver on Mac; friends/demo audience |
| **Commercial launch** | **Waitlist only** — no Stripe/license gate in code yet | Future paying customers |

**Verified on Mac-Mini-2 (June 2026):**
- Desk Health: **100/100 (A)** when Docker Model Runner is up and corpus is fresh
- DMR: 2 local models (`smollm2`, `devstral-small-2`) on port **12434**
- Knowledge corpus: **99 pages**, RAG: **100 markdown docs**
- Menu bar app + dashboard at **http://127.0.0.1:8765**
- Smart Handoff generates paste-ready Cursor prompts

**The core problem LEMdesk solves:** Cursor and similar AI IDEs do not sync project context, local model URLs, or agent state across machines or rooms. LEMdesk wires your **local model endpoint**, **documentation corpus**, **MCP tools**, and **session handoff** so you can move desks without re-explaining everything to the agent.

---

## 2. Product positioning

**LEMdev** is the company. **LEMdesk** is the product. Tagline: *"Same desk on any room."*

### Starter vs Pro

| Feature | Starter (free) | Pro (planned $19/mo) |
|---------|----------------|------------------------|
| Knowledge scrape + RAG | CLI | CLI + menu bar trigger |
| MCP server for Cursor | Yes | Yes |
| Session handoff | Manual markdown | **Smart Handoff** desk pack + clipboard |
| Desk Health score | CLI only | **Live menu bar** + web dashboard |
| Morning startup | Manual | **`lemdesk-desk-up`** one command |
| Telemetry | None (self-hosted) | None (self-hosted) |

Pro code currently ships in the open repo as a **demo build** — commercial launch needs a license key or private package.

---

## 3. System architecture

### 3.1 High-level diagram (conceptual)

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR LAN / DESK                         │
├─────────────────────────────────────────────────────────────────┤
│  Cursor IDE  ──MCP──►  lemdesk_mcp_server.py                   │
│       │                    │ search docs, handoff, AI paths      │
│       └── Models API ──►  Docker Model Runner :12434             │
│                              (local LLM — no cloud API key)     │
├─────────────────────────────────────────────────────────────────┤
│  LEMdesk Starter          │  LEMdesk Pro                        │
│  • scrape_lemdesk.py      │  • desk_health.py (0–100 score)    │
│  • lemdesk_auto.py sync   │  • desk_up.py (morning startup)    │
│  • knowledge.json + RAG   │  • menubar.py (macOS)              │
│  • session_handoff.md     │  • status_server.py (:8765)        │
│                           │  • smart_handoff.py (desk pack)    │
├─────────────────────────────────────────────────────────────────┤
│  STORAGE (Mac Mini example — small internal SSD)                 │
│  Internal SSD  → code + Cursor config only                       │
│  GC-MM2 USB    → Docker engine, DMR models (~15GB), Pro backup │
│  NAS (SMB)     → shared skills, RAG, rules, backups            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component map

| Component | File / path | Role |
|-----------|-------------|------|
| CLI hub | `bot.py` | Single entry for crypto bot + all LEMdesk commands |
| Auto pipeline | `lemdesk_auto.py` | Scrape → RAG → briefs → handoff in one shot |
| Doc scraper | `scrape_lemdesk.py` | BFS crawl of Docker AI docs into `lemdesk/data/` |
| Knowledge base | `lemdesk/data/knowledge.json` | Structured page corpus |
| RAG docs | `lemdesk/data/rag_docs/*.md` | BM25-searchable markdown |
| MCP server | `lemdesk_mcp_server.py` | Cursor tools: search, handoff, AI path doctor |
| Path registry | `lemdesk/path_registry.py` | Logical paths (skills, rag, NAS) per machine |
| Pro health | `lemdesk_pro/desk_health.py` | Scores DMR, corpus, RAG, handoff, MCP |
| Pro startup | `lemdesk_pro/desk_up.py` | Docker + DMR + mount checks |
| Pro UI | `lemdesk_pro/menubar.py` | macOS menu bar + notifications |
| Pro dashboard | `lemdesk_pro/static/dashboard.html` | Local web UI at :8765 |
| Smart Handoff | `lemdesk_pro/smart_handoff.py` | `desk_pack.json` + `desk_handoff_prompt.md` |

### 3.3 Data flow — daily workflow

1. **Morning:** `python3 bot.py lemdesk-desk-up` — starts Docker, enables Model Runner, checks GC-MM2/NAS mounts, prints health.
2. **Work in Cursor** — local model at `http://localhost:12434/engines/v1`, MCP tools search your corpus.
3. **Sync (optional):** `python3 bot.py lemdesk-sync --fast` — refreshes docs from Docker AI sites.
4. **Switch rooms:** Menu bar **Smart Handoff** → prompt copied → paste in new Cursor chat.
5. **Glance status:** Menu bar shows `100A` or open dashboard at :8765.

### 3.4 Cross-machine strategy

| What syncs | How |
|------------|-----|
| Skills, agents, rules | NAS mirror at `/Volumes/docker/AI` or Git |
| Knowledge + RAG | `lemdesk-sync` on each machine or NAS copy |
| Cursor chat history | **Not native** — use Smart Handoff instead |
| Model weights | Docker `docker model pull` per machine, or shared GC-MM2 symlink layout |
| Secrets | `~/.config/cursor-crypto/secrets.env` — never in Git |

---

## 4. Installation guide

### 4.1 Prerequisites

- **macOS** (menu bar Pro) or Linux/Windows (CLI dashboard only)
- **Python 3.10+**
- **Docker Desktop 4.40+** with Model Runner
- **Cursor IDE** (primary AI editor for this deployment)
- **Optional:** Synology/NAS SMB share for shared AI corpus
- **Optional:** External USB SSD (e.g. GC-MM2) if internal disk is small

### 4.2 Fresh install — GitHub (Starter + Pro)

```bash
git clone https://github.com/billrilea-lab/LemDesk.git
cd LemDesk
python3 -m pip install -r requirements.txt
# macOS menu bar:
python3 -m pip install rumps
```

### 4.3 Configure Docker Model Runner

```bash
./lemdesk/scripts/configure_docker_desktop.sh
```

Or manually:
1. Docker Desktop → **Settings → AI** → Enable **Docker Model Runner**
2. Enable **host-side TCP** on port **12434**
3. Pull models:
   ```bash
   docker model pull ai/smollm2
   docker model pull ai/devstral-small-2
   ```
4. Verify: `./lemdesk/scripts/check_dmr.sh`

### 4.4 Wire Cursor to local models

**Cursor → Settings → Models → OpenAI-compatible API**

| Field | Value |
|-------|--------|
| Base URL | `http://localhost:12434/engines/v1` |
| API Key | `not-needed` |
| Model | `docker.io/ai/devstral-small-2:latest` |

### 4.5 Wire Cursor MCP (knowledge search)

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "lemdesk-kb": {
      "command": "python3",
      "args": ["/full/path/to/lemdesk_mcp_server.py"]
    }
  }
}
```

Reload Cursor. Available tools: `search_lemdesk_docs`, `get_lemdesk_handoff`, `get_lemdesk_setup_facts`, `resolve_ai_path`, `ai_path_doctor`, `list_lemdesk_topics`.

### 4.6 AI path registry (multi-drive / NAS)

```bash
python3 bot.py ai-paths init
python3 bot.py ai-paths wizard    # interactive — mount NAS first in Finder
python3 bot.py ai-paths doctor    # expect 100/100 when mounts OK
```

Config lives at `~/.config/lemdesk/ai_paths.yaml`.

**Mac-Mini-2 reference layout:**
- NAS: `/Volumes/docker/AI`
- Fast cache: `/Volumes/GC-MM2/AI-Local`
- Docker models: `~/.docker/models` → `/Volumes/GC-MM2/Docker/models`
- Pro backup: `/Volumes/GC-MM2/lemdev.com/LemDesk/Pro`

### 4.7 Mac Mini — small internal SSD

```bash
./lemdesk/scripts/relocate_storage.sh --apply
```

Moves ~15GB DMR model weights off the internal drive to GC-MM2. See `.cursor/skills/docker-mac-storage/SKILL.md`.

### 4.8 First run

```bash
python3 bot.py lemdesk-desk-up          # morning startup
python3 bot.py lemdesk-sync --fast      # populate knowledge corpus
python3 bot.py lemdesk-health           # expect 85–100
python3 bot.py lemdesk-pro              # menu bar + dashboard
```

---

## 5. Command reference

| Command | Purpose |
|---------|---------|
| `lemdesk-desk-up` | Docker + DMR + mounts + health |
| `lemdesk-desk-up --sync` | Above + full corpus sync |
| `lemdesk-desk-up --mount-nas` | Open NAS mount dialog if missing |
| `lemdesk-health` | 0–100 desk score |
| `lemdesk-sync --fast` | Quick scrape + RAG + handoff |
| `lemdesk-smart-handoff` | Desk pack + agent prompt |
| `lemdesk-handoff` | Simple markdown handoff |
| `lemdesk-pro` | Menu bar + :8765 dashboard |
| `lemdesk-pro --cli` | Dashboard only (no menu bar) |
| `lemdesk-search <query>` | Search knowledge base |
| `lemdesk-review` | Refresh briefs + topology runbook |
| `ai-paths doctor` | Check all logical paths |
| `ai-paths wizard` | Setup NAS/local paths |
| `lemdesk-backup-gc` | Mirror Pro to GC-MM2 backup folder |

Module form: `python3 -m lemdesk_pro {health|desk-up|menubar|smart-handoff}`

---

## 6. Desk Health scoring (Pro)

Maximum **100 points** from six checks:

| Check | Max points | Pass condition |
|-------|------------|----------------|
| Docker Model Runner | 25 | HTTP 200 on :12434/models |
| Knowledge corpus | 20 | ≥50 pages, updated <7 days |
| RAG index | 15 | ≥40 markdown docs |
| Session handoff | 15 | handoff file <72h old |
| MCP server | 15 | `lemdesk_mcp_server.py` exists |
| Scrape staging | 10 | OK if corpus fresh (staging files normal) |

**Grades:** A ≥85 · B ≥65 · C ≥40 · D below 40

---

## 7. Storage topology (reference deployment)

```
Internal SSD (228GB Mac Mini)
├── /Users/williamrilea/Cursor- Crypto/     # monorepo (live dev)
├── ~/.cursor/                               # Cursor config (small)
└── (no Docker models — symlinked out)

GC-MM2 USB SSD (/Volumes/GC-MM2)
├── Docker/                                  # Docker Desktop disk image
├── Docker/models/                           # DMR weights (~15GB)
├── AI-Local/                                # rag-cache, scratch
└── lemdev.com/LemDesk/Pro/                  # offline Pro backup mirror

NAS SMB (/Volumes/docker)
└── AI/
    ├── skills/ agents/ rules/ rag/
    ├── backups/lemdesk/
    └── lemdesk/data/ logs/
```

---

## 8. Business model & go-to-market

1. **Starter on GitHub** — free, builds trust, no signup wall
2. **Demo wow** — menu bar `100A` + live dashboard screenshot
3. **Waitlist at lemdev.com/pricing** — FormSubmit → hello@lemdev.com
4. **Pro launch** — Stripe + license key (not implemented yet)
5. **Team tier** — multi-machine fleet health (roadmap)

**Revenue → compute:** 26 Pro subscribers ≈ $500/mo → funds GPU or second Mac Mini.

---

## 9. What is complete vs roadmap

### Complete (working today)

- [x] Doc scrape + knowledge corpus + RAG
- [x] MCP server for Cursor
- [x] Session handoff + Smart Handoff desk packs
- [x] Desk Health scoring
- [x] Desk Up morning startup (`--heal`, `--mirror-nas`)
- [x] macOS menu bar app + local dashboard
- [x] AI path registry (NAS auto-detect)
- [x] Docker storage relocate for small SSD
- [x] GC-MM2 offline backup mirror
- [x] **One-shot install** (`lemdesk-install`)
- [x] **Login LaunchAgent** (`install_login_item.sh`)
- [x] **Cursor auto-handoff rule** (`.cursor/rules/lemdesk-desk.mdc`)
- [x] **Pro license gate** (`lemdesk-license`, `--dev` bypass)
- [x] **NAS mirror on sync** (`nas_mirror.py`)
- [x] lemdev.com marketing site (GitHub Pages)
- [x] LemDesk public GitHub repo

### Roadmap (not blocking personal use)

- [ ] Stripe Payment Link on pricing page (see `PRO_COMMERCE.md`)
- [ ] Automated license fulfillment webhook
- [ ] Windows-native menu bar (CLI dashboard works today)
- [ ] Team dashboard / fleet health

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| DMR unreachable | `open -a Docker` then `docker desktop enable model-runner` |
| Models on internal SSD | `./lemdesk/scripts/relocate_storage.sh --apply` |
| `docker model ls` empty after move | Flatten `GC-MM2/Docker/models/models/` — see docker-mac-storage skill |
| NAS paths 76/100 | Mount NAS in Finder; update `ai_paths.yaml` to `/Volumes/docker/AI` |
| Menu bar won't start | Port :8765 in use — quit existing `lemdesk-pro` or use `--cli` |
| Health 95 not 100 | Run `lemdesk-sync --fast` if corpus stale |
| Cursor can't find MCP | Full path in `mcp.json`; restart Cursor |

---

## 11. Security & privacy

- **Self-hosted** — no LEMdev cloud; data stays on your machines
- **Secrets** in `~/.config/` — excluded from Git
- **DMR** — expose :12434 on trusted LAN only
- **Not affiliated** with Docker, Cursor, Anthropic, or OpenAI

---

## 12. File locations quick reference

| Artifact | Path |
|----------|------|
| Handoff markdown | `lemdesk/logs/session_handoff.md` |
| Smart Handoff prompt | `lemdesk/logs/desk_handoff_prompt.md` |
| Desk pack JSON | `lemdesk/logs/desk_pack.json` |
| Agent runbook | `lemdesk/logs/lemdesk_agent_context.md` |
| AI paths config | `~/.config/lemdesk/ai_paths.yaml` |
| MCP config | `~/.cursor/mcp.json` |
| This report | `lemdesk/LEMdesk_SYSTEM_REPORT.md` |
| Setup guide | `lemdesk/SETUP.md` |
| AI paths guide | `lemdesk/AI_PATHS.md` |

---

## 13. NotebookLM usage notes

**Suggested NotebookLM prompts after upload:**
- "Explain LEMdesk to a developer friend in five minutes."
- "Walk through installation on a Mac Mini with a small SSD and a NAS."
- "What is the difference between Starter and Pro?"
- "How does Smart Handoff solve the cross-room Cursor problem?"
- "Create a troubleshooting FAQ from section 10."
- "Explain the storage layout and why Docker models live on GC-MM2."

**Companion files to upload for richer sources:** `SETUP.md`, `AI_PATHS.md`, `README.md`, `lemdev-site/index.html` (export or paste marketing copy).

---

*End of LEMdesk System Report — LEMdev © 2026*
