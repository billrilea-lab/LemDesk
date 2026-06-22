# LEMdesk

**LEMdesk — same desk on any room.** By [LEMdev](https://lemdev.com).

| Edition | What it is |
|---------|------------|
| **Starter** (free) | Open-source **sample kit** — CLI sync, RAG, MCP, manual handoff markdown |
| **Pro** ($19/mo) | The **full desk** — menu bar health, Smart Handoff desk packs, live dashboard |

Start with Starter to prove local sync works. Upgrade to Pro for the version you actually live in.

## What you get

| Piece | Purpose |
|-------|---------|
| `lemdesk/data/` | Scraped knowledge corpus, RAG markdown, setup facts |
| `lemdesk/logs/` | Agent brief, runbook, session handoff, Super App index |
| `lemdesk/scripts/` | DMR probe, auto pipeline, Open WebUI, supervisor launcher |
| `lemdesk/agents/` | Multi-agent YAML with BM25 RAG over your corpus |
| `lemdesk_mcp_server.py` | Cursor MCP tools for local KB search |
| `scrape_lemdesk.py` | BFS doc scrape (httpx / crawl4ai) |
| `lemdesk_auto.py` | One-shot sync pipeline |

## Quick start

```bash
# From repo root (monorepo or standalone clone)
pip install -r requirements.txt

# One-shot: scrape (smart) + RAG + briefs + handoff
python3 lemdesk_auto.py --skip-dmr-check --fast

# Or via crypto bot wrapper (if present)
python3 bot.py lemdesk-sync --fast --skip-dmr-check

# Point Cursor → Models → OpenAI
#   API key: not-needed
#   Base URL: http://<server-ip>:12434/engines/v1
#   Model: ai/qwen2.5-coder (or similar ai/* model)
```

Verify local model endpoint:

```bash
./lemdesk/scripts/check_dmr.sh
```

Session handoff before changing rooms:

```bash
python3 bot.py lemdesk-handoff --focus "what you were doing"
# → lemdesk/logs/session_handoff.md
```

## LEMdesk Pro (demo)

Menu bar health score, local dashboard, and Smart Handoff desk packs:

```bash
python3 -m lemdesk_pro health
python3 -m lemdesk_pro smart-handoff
python3 -m lemdesk_pro menubar          # macOS menu bar + http://127.0.0.1:8765
./lemdesk/scripts/run_pro.sh
```

Pro waitlist: [lemdev.com/pricing.html](https://lemdev.com/pricing.html)

## MCP (Cursor)

Copy `lemdesk/mcp/cursor_mcp.json.example` into `~/.cursor/mcp.json` and set the full path to `lemdesk_mcp_server.py`.

Tools: `search_lemdesk_docs`, `get_lemdesk_handoff`, `get_lemdesk_setup_facts`, `list_lemdesk_topics`.

## Supervisor agent

Requires Docker Desktop Model Runner + `docker agent` CLI:

```bash
./lemdesk/scripts/run_supervisor.sh
```

See `lemdesk/agents/README.md`.

## Optional shared chat

```bash
./lemdesk/scripts/run_open_webui.sh
```

## Cross-machine sync

- User-level agents/skills: [agents_sync](https://github.com/CognitiveSand/agents_sync)
- Git: commit `lemdesk/agents/` and `.cursor/skills/lemdesk/`
- Chat history is **not** native in Cursor — use handoff + optional Open WebUI

## GitHub

Public repo: [github.com/billrilea-lab/LemDesk](https://github.com/billrilea-lab/LemDesk)

Website: [lemdev.com](https://lemdev.com)

## License

MIT — see [LICENSE](LICENSE). Independent project; not affiliated with Docker, Cursor, Anthropic, or OpenAI.
