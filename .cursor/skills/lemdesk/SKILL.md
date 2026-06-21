# LEMdesk — same desk on any room

Free LAN kit for local models, agent sync, knowledge search, and session handoff. By LEMdev.

Use when working on **LEMdesk**, **local Model Runner / LAN endpoints**, **session handoff**, **MCP doc search**, or **cross-room AI setup** (Cursor, Claude, Gemini on a home network).

## Hub: `lemdesk/`

| Path | Purpose |
|------|---------|
| `incoming/` | Scrape staging (per-URL JSON) |
| `data/knowledge.json` | Scraped docs corpus |
| `data/setup_facts.json` | Ports, URLs, models, CLI snippets |
| `data/topology_comparison.json` | Single-server vs per-desktop vs hybrid |
| `data/gordon_playbook.json` | Workflow patterns + example prompts |
| `agents/lemdesk_supervisor.yaml` | Local multi-agent supervisor |
| `scripts/` | `check_dmr.sh`, `lemdesk_auto.sh`, `run_supervisor.sh` |
| `logs/lemdesk_agent_context.md` | Human runbook |
| `logs/super_app_knowledge_index.json` | Links gobabytrade + lemdesk corpora |

## One command sync (recommended)

```bash
python3 bot.py lemdesk-sync              # smart: extra-seeds if corpus < 7 days old
python3 bot.py lemdesk-sync --fast       # full scrape, max speed (httpx, no raw HTML)
python3 bot.py lemdesk-sync --full       # full BFS with auto backend
./lemdesk/scripts/lemdesk_auto.sh --fast
python3 lemdesk_auto.py --skip-dmr-check --fast   # standalone (no bot.py)
```

Weekly schedule (macOS): `./lemdesk/scripts/install_auto_schedule.sh`

## Scrape (manual)

```bash
python3 scrape_lemdesk.py --backend auto --workers 8 --max-depth 2 --post-process
```

- `--backend httpx` — fast static docs (recommended for bulk)
- `--merge-only` — rebuild knowledge.json from `incoming/` without fetching

## LAN model endpoint quick setup

1. Enable local OpenAI-compatible API on your server (e.g. TCP on `:12434`)
2. Verify: `./lemdesk/scripts/check_dmr.sh`
3. Cursor: Settings → Models → OpenAI API Key
   - Key: `not-needed`
   - Base URL: `http://localhost:12434/engines/v1` (or `http://<server-ip>:12434/engines/v1` on LAN)
   - Model: `ai/qwen2.5-coder` or `ai/glm-4.7-flash`

See `lemdesk/scripts/client_cursor_env.example`.

## Topology decision

Read `lemdesk/data/topology_comparison.json` or run:

```bash
python3 bot.py lemdesk-review
```

## Cross-machine sync (agents, skills, MCP)

Cursor does **not** natively sync skills/agents. Use:

1. **[agents_sync](https://github.com/CognitiveSand/agents_sync)** — Cursor, Claude, Gemini user-level files
2. **Git** — commit `lemdesk/agents/` and `.cursor/skills/lemdesk/`
3. **Optional gist sync** — paths in `lemdesk/scripts/cursor_sync_paths.json`

**Not synced natively:** chat history, Cursor cloud User Rules, SQLite state.

## Local supervisor (DMR + BM25 RAG)

Uses **local models** + **BM25 RAG** over `lemdesk/data/rag_docs/` (refresh via `lemdesk-review`).

```bash
./lemdesk/scripts/run_supervisor.sh
```

Requires `docker agent` CLI and a pulled local model (`ai/qwen2.5-coder`). RAG index: `lemdesk/data/rag_bm25.db`.

## Open WebUI (shared chat across rooms)

```bash
./lemdesk/scripts/run_open_webui.sh
# → http://localhost:3000 (or http://<server-ip>:3000)
```

## MCP knowledge server (Cursor)

Copy `lemdesk/mcp/cursor_mcp.json.example` → merge into `~/.cursor/mcp.json`.

Tools: `search_lemdesk_docs`, `get_lemdesk_handoff`, `get_lemdesk_setup_facts`, `list_lemdesk_topics`.

```bash
python3 lemdesk_mcp_server.py   # stdio MCP (Cursor launches this)
```

## Session handoff (another room)

```bash
python3 bot.py lemdesk-handoff --focus "birdseed review" --notes "testing glm on DMR"
```

On the other machine: open `lemdesk/logs/session_handoff.md` or MCP `get_lemdesk_handoff`.

## Search KB without supervisor

```bash
python3 lemdesk_brief.py search "sbx policy host.docker.internal"
python3 bot.py lemdesk-search sbx policy
```

## BirdSeed + local model

See `.cursor/skills/birdseed-trade/SKILL.md` — point Cursor at your LAN model then `birdseed-review`.

```bash
python3 bot.py lemdesk-review
python3 bot.py birdseed-review
```

## Re-scrape cadence

Re-sync monthly or after major desktop/runtime updates:

```bash
python3 scrape_lemdesk.py --extra-seeds --post-process
python3 scrape_lemdesk.py --backend httpx --workers 6 --max-depth 2 --post-process
```
