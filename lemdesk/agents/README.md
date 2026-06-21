# LEMdesk supervisor

Local multi-agent team inspired by Gordon patterns — uses scraped knowledge in `lemdesk/data/`.

## Prerequisites

- Docker Desktop 4.74+ with **Model Runner** enabled (`docker model pull ai/qwen2.5-coder`)
- `docker agent` CLI
- Re-scrape + RAG export: `python3 bot.py lemdesk-review`

## Models

Supervisor uses **local DMR** (`provider: dmr`) — not cloud OpenAI. RAG uses BM25 over `lemdesk/data/rag_docs/`.

## Run

```bash
chmod +x lemdesk/scripts/*.sh
./lemdesk/scripts/run_supervisor.sh
```

Or:

```bash
docker agent run lemdesk/agents/lemdesk_supervisor.yaml
```

## Agents

| Agent | Role |
|-------|------|
| `root` | Routes questions to specialists |
| `dmr_expert` | Model Runner, LAN URLs, Cursor integration |
| `sandbox_expert` | SBX isolation, `sbx policy`, host.docker.internal |
| `gordon_patterns` | Container debug, Dockerfile review workflows |

Shell tools require approval in Docker Agent (same permission model as Gordon).

## Open WebUI (shared chat)

```bash
./lemdesk/scripts/run_open_webui.sh
```

## MCP for Cursor

See `lemdesk/mcp/cursor_mcp.json.example` and `lemdesk_mcp_server.py`.

## Session handoff

`python3 bot.py lemdesk-handoff` → `lemdesk/logs/session_handoff.md`

## Sync across desktops

- User-level: [agents_sync](https://github.com/CognitiveSand/agents_sync)
- Repo: commit `lemdesk/agents/` and `.cursor/skills/lemdesk/`
- See `lemdesk/scripts/cursor_sync_paths.json`
- Optional: `./lemdesk/scripts/install_agents_sync.sh`
