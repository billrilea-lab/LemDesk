# LEMdesk — agent context

Generated: 2026-06-21T22:36:53.936491+00:00

## Hub layout

- `lemdesk/incoming/` — scrape staging
- `lemdesk/data/` — knowledge + facts
- `lemdesk/agents/` — Docker Agent YAML
- `lemdesk/scripts/` — LAN tooling
- `lemdesk/logs/` — briefs and index

## Point Cursor at LAN Model Runner

| Setting | Value |
|---------|-------|
| OpenAI API Key | `not-needed` |
| Override OpenAI Base URL (local) | `http://localhost:12434/engines/v1` |
| Override OpenAI Base URL (LAN client) | `http://<server-ip>:12434/engines/v1` |

## Topology decision tree

### Single model server
- **When:** One powerful Mac (Apple Silicon); other rooms are thin clients
- **Config:** {
"server": "docker desktop enable model-runner --tcp 12434",
"client_cursor_base_url": "http://<server-lan-ip>:12434/engines/v1",
"cors": "Add client origins in Docker Desktop > AI > CORS"
}

### Per-desktop Model Runner
- **When:** Each machine has enough RAM; minimal LAN coupling
- **Config:** {
"every_desktop": "http://localhost:12434/engines/v1",
"sync": "Use agents_sync for agents/skills/MCP \u2014 not models"
}

### Hybrid
- **When:** Large models on server, fast small models local
- **Config:** {
"server_models": [
"ai/qwen3-coder",
"ai/devstral-small-2"
],
"local_models": [
"ai/smollm2",
"ai/llama3.2"
],
"sync": "agents_sync for shared agent YAML in lemdesk/agents/"
}

## Session continuity (honest limits)

- **Models:** shared DMR URL or per-desktop localhost
- **Agents/skills/MCP:** agents_sync + `lemdesk/agents/` in Git
- **Project:** this repo + generated briefs
- **Chat history:** not native — use Open WebUI or cursor-sync extensions

## Commands

- `scrape`: python3 scrape_lemdesk.py --backend auto --workers 8 --max-depth 2 --post-process
- `check_dmr`: lemdesk/scripts/check_dmr.sh
- `run_supervisor`: lemdesk/scripts/run_supervisor.sh
- `auto_pipeline`: python3 bot.py lemdesk-sync
- `auto_fast`: python3 bot.py lemdesk-sync --fast
- `search_kb`: python3 lemdesk_brief.py search 'sbx policy'
- `open_webui`: lemdesk/scripts/run_open_webui.sh
- `session_handoff`: python3 bot.py lemdesk-handoff
- `mcp_server`: lemdesk_mcp_server.py — see lemdesk/mcp/cursor_mcp.json.example
- `birdseed_with_local_model`: Cursor: Override OpenAI Base URL http://localhost:12434/engines/v1, model ai/glm-4.7-flash

## Sandboxes + DMR

Sandboxes block host localhost by default. For SBX agents hitting LAN DMR: sbx policy allow network host:12434 and use http://host.docker.internal:12434 inside sandbox.

## Re-scrape

```bash
python3 scrape_lemdesk.py --backend auto --workers 8 --max-depth 2 --post-process
```

## Local KB search (no docker agent)

```bash
python3 lemdesk_brief.py search 'model runner cursor'
```
