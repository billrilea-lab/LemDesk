"""LEMdesk knowledge briefs, topology comparison, and Super App index."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
HUB = ROOT / "lemdesk"
DATA_DIR = HUB / "data"
LOGS_DIR = HUB / "logs"
KNOWLEDGE_PATH = DATA_DIR / "knowledge.json"
GBT_KNOWLEDGE = ROOT / "data" / "gobabytrade" / "knowledge.json"

SETUP_FACTS = DATA_DIR / "setup_facts.json"
GORDON_PLAYBOOK = DATA_DIR / "gordon_playbook.json"
TOPOLOGY = DATA_DIR / "topology_comparison.json"
RAG_DOCS_DIR = DATA_DIR / "rag_docs"
RAG_INDEX_META = DATA_DIR / "rag_index_meta.json"
AGENT_BRIEF = LOGS_DIR / "lemdesk_agent_brief.json"
AGENT_CONTEXT = LOGS_DIR / "lemdesk_agent_context.md"
SUPER_APP_INDEX = LOGS_DIR / "super_app_knowledge_index.json"
SESSION_HANDOFF = LOGS_DIR / "session_handoff.md"
HANDOFF_TEMPLATE = LOGS_DIR / "session_handoff.template.md"

PORT_RE = re.compile(r"\b12434\b")
BASE_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
ENV_RE = re.compile(r"\b([A-Z][A-Z0-9_]+(?:_BASE_URL|_API_KEY|_API_BASE))\b")
MODEL_RE = re.compile(r"\bai/[a-z0-9._-]+", re.I)
KNOWN_MODELS = [
    "ai/qwen3-coder",
    "ai/qwen2.5-coder",
    "ai/devstral-small-2",
    "ai/glm-4.7-flash",
    "ai/llama3.2",
    "ai/smollm2",
    "ai/all-minilm",
    "ai/qwen3",
]
CLI_RE = re.compile(r"(?:^|\n)\s*(?:\$|>)\s*(docker\s+(?:model|ai|agent|mcp|desktop)\s+[^\n]+)", re.M)
SBX_RE = re.compile(r"sbx\s+[a-z][^\n`\"]{5,80}", re.I)
DMR_URL_HINTS = ("12434", "model-runner", "engines/v1", "model-runner.docker.internal")


def load_knowledge(path: Path | None = None) -> dict:
    p = path or KNOWLEDGE_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def extract_setup_facts(knowledge: dict) -> dict:
    pages = knowledge.get("pages", {})
    corpus_parts: list[str] = []
    for p in pages.values():
        corpus_parts.append(p.get("markdown") or "")
        corpus_parts.append(p.get("text_sample") or "")
    corpus = "\n".join(corpus_parts)

    ports = sorted(set(PORT_RE.findall(corpus)))
    all_urls = sorted(set(BASE_URL_RE.findall(corpus)))
    base_urls = [
        u.rstrip(".,);]")
        for u in all_urls
        if any(h in u.lower() for h in DMR_URL_HINTS)
    ]
    env_vars = sorted(set(ENV_RE.findall(corpus)))
    models_found = sorted(set(MODEL_RE.findall(corpus)))
    models = sorted(set(models_found + [m for m in KNOWN_MODELS if m in corpus] + KNOWN_MODELS))
    cli_cmds = [m.strip() for m in CLI_RE.findall(corpus)][:60]
    sbx_cmds = sorted(set(SBX_RE.findall(corpus)))[:30]

    cursor_block = {
        "openai_api_key": "not-needed",
        "override_openai_base_url_local": "http://localhost:12434/engines/v1",
        "override_openai_base_url_lan": "http://<server-ip>:12434/engines/v1",
        "anthropic_base_url_local": "http://localhost:12434",
        "model_id_examples": [
            m for m in models if any(x in m for x in ("coder", "llama", "glm", "devstral", "smollm"))
        ][:10],
        "notes": [
            "Use full model name with ai/ prefix",
            "Enable host-side TCP in Docker Desktop Settings > AI",
            "Add CORS origins for browser-based tools",
        ],
    }

    return {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "ports": ports or ["12434"],
        "base_urls": base_urls,
        "env_vars": env_vars,
        "models": models,
        "cli_commands_sample": cli_cmds,
        "sbx_commands_sample": sbx_cmds,
        "cursor_integration": cursor_block,
        "dmr_defaults": {
            "tcp_port": 12434,
            "openai_compatible_base": "http://localhost:12434/engines/v1",
            "ollama_compatible_base": "http://localhost:12434",
            "container_base": "http://model-runner.docker.internal",
        },
    }


def _safe_slug(url: str, title: str) -> str:
    parsed = urlparse(url)
    slug = re.sub(r"[^\w.-]+", "_", (parsed.netloc + parsed.path).strip("/"))[:100]
    if not slug:
        slug = re.sub(r"[^\w.-]+", "_", title[:60]) or "page"
    return slug


def export_rag_corpus(knowledge: dict) -> dict:
    """Export scraped pages as markdown files for Docker Agent BM25 RAG."""
    RAG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    pages = knowledge.get("pages", {})
    written: list[str] = []
    for url, page in sorted(pages.items()):
        title = page.get("title") or page.get("h1") or url
        body = page.get("markdown") or page.get("text_sample") or ""
        if len(body.strip()) < 80:
            continue
        slug = _safe_slug(url, title)
        path = RAG_DOCS_DIR / f"{slug}.md"
        content = f"# {title}\n\nSource: {url}\nTopic: {page.get('topic', 'general')}\n\n{body.strip()}\n"
        path.write_text(content)
        written.append(str(path.relative_to(ROOT)))

    # Also export structured facts as a single doc for keyword hits
    if SETUP_FACTS.exists():
        facts_path = RAG_DOCS_DIR / "setup_facts.md"
        facts = json.loads(SETUP_FACTS.read_text())
        facts_path.write_text(
            "# Docker AI setup facts (extracted)\n\n```json\n"
            + json.dumps(facts, indent=2)
            + "\n```\n"
        )
        written.append(str(facts_path.relative_to(ROOT)))

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(written),
        "docs_dir": str(RAG_DOCS_DIR.relative_to(ROOT)),
        "files": written,
    }
    RAG_INDEX_META.write_text(json.dumps(meta, indent=2))
    return meta


def search_knowledge(query: str, knowledge: dict | None = None, limit: int = 8) -> list[dict]:
    """Simple BM25-ish keyword search over page text (CLI / Super App helper)."""
    k = knowledge or load_knowledge()
    terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    if not terms:
        return []

    scored: list[tuple[float, str, dict]] = []
    for url, page in k.get("pages", {}).items():
        text = (page.get("markdown") or page.get("text_sample") or "").lower()
        score = sum(text.count(t) for t in terms)
        title = (page.get("title") or page.get("h1") or "").lower()
        score += sum(3 for t in terms if t in title)
        if score > 0:
            scored.append((score, url, page))

    scored.sort(key=lambda x: -x[0])
    out: list[dict] = []
    for score, url, page in scored[:limit]:
        out.append(
            {
                "score": score,
                "url": url,
                "title": page.get("title") or page.get("h1"),
                "topic": page.get("topic"),
                "snippet": (page.get("text_sample") or "")[:400],
            }
        )
    return out


def build_topology_comparison() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "patterns": [
            {
                "id": "single_model_server",
                "name": "Single model server",
                "when_it_wins": "One powerful Mac (Apple Silicon); other rooms are thin clients",
                "pros": [
                    "One model copy in RAM/GPU",
                    "Consistent model across all clients",
                    "Easier to run largest quant models",
                ],
                "cons": [
                    "LAN dependency and latency",
                    "Server must stay on",
                    "Firewall/TCP exposure needs care",
                ],
                "key_config": {
                    "server": "docker desktop enable model-runner --tcp 12434",
                    "client_cursor_base_url": "http://<server-lan-ip>:12434/engines/v1",
                    "cors": "Add client origins in Docker Desktop > AI > CORS",
                },
            },
            {
                "id": "per_desktop_dmr",
                "name": "Per-desktop Model Runner",
                "when_it_wins": "Each machine has enough RAM; minimal LAN coupling",
                "pros": [
                    "No cross-room network dependency",
                    "localhost latency",
                    "Works if Wi-Fi is flaky",
                ],
                "cons": [
                    "Duplicate model pulls per machine",
                    "RAM/GPU multiplied",
                    "Models may differ between desks",
                ],
                "key_config": {
                    "every_desktop": "http://localhost:12434/engines/v1",
                    "sync": "Use agents_sync for agents/skills/MCP — not models",
                },
            },
            {
                "id": "hybrid",
                "name": "Hybrid",
                "when_it_wins": "Large models on server, fast small models local",
                "pros": [
                    "Best of both for speed vs capability",
                    "Fallback if server offline",
                ],
                "cons": [
                    "Two endpoints to configure per client",
                    "More operational complexity",
                ],
                "key_config": {
                    "server_models": ["ai/qwen3-coder", "ai/devstral-small-2"],
                    "local_models": ["ai/smollm2", "ai/llama3.2"],
                    "sync": "agents_sync for shared agent YAML in lemdesk/agents/",
                },
            },
        ],
        "sandbox_network_note": (
            "Sandboxes block host localhost by default. For SBX agents hitting LAN DMR: "
            "sbx policy allow network host:12434 and use http://host.docker.internal:12434 inside sandbox."
        ),
        "session_continuity": {
            "models": "Shared DMR endpoint or per-machine localhost",
            "agents_skills_mcp": "agents_sync or Git — ~/.cursor/ and lemdesk/agents/",
            "project_context": "Git repo + logs/*_agent_context.md + session_handoff.md",
            "chat_history": "Open WebUI on model server (port 3000) or cursor-sync extensions",
            "open_webui": "lemdesk/scripts/run_open_webui.sh → http://localhost:3000",
            "mcp_kb": "lemdesk_mcp_server.py — see lemdesk/mcp/cursor_mcp.json.example",
        },
    }


def build_gordon_playbook(knowledge: dict) -> dict:
    gordon_pages = {
        url: p for url, p in knowledge.get("pages", {}).items() if p.get("topic") == "gordon"
    }
    examples = []
    for page in gordon_pages.values():
        text = page.get("markdown") or page.get("text_sample") or ""
        for line in text.splitlines():
            low = line.lower()
            if "docker ai" in low or "what containers" in low or "dockerfile" in low:
                if len(line.strip()) > 10:
                    examples.append(line.strip()[:200])
    examples = list(dict.fromkeys(examples))[:25]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_pages": len(gordon_pages),
        "surfaces": [
            "Docker Desktop sidebar (Gordon)",
            "CLI: docker ai",
            "hub.docker.com Gordon icon",
            "docs.docker.com Gordon icon",
        ],
        "capabilities": [
            "Explain Docker concepts and commands",
            "Search Docker docs and web",
            "Write/modify Dockerfiles",
            "Debug containers via logs",
            "Manage containers, images, volumes, networks",
        ],
        "permission_model": "Proposes actions before execute; session-scoped approvals; reset each session",
        "example_prompts": examples or [
            "What containers are running?",
            "Review my Dockerfile for best practices",
            "show me logs from my nginx container",
            "list my local images and their sizes",
        ],
        "local_alternative": {
            "path": "lemdesk/agents/lemdesk_supervisor.yaml",
            "run": "lemdesk/scripts/run_supervisor.sh",
            "note": "Local Docker Agent team using scraped KB — not Gordon SaaS",
        },
    }


def build_super_app_index() -> dict:
    sources: list[dict] = []
    for label, path, topic in [
        ("gobabytrade", GBT_KNOWLEDGE, "crypto_trading"),
        ("lemdesk", KNOWLEDGE_PATH, "lemdesk"),
    ]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        sources.append(
            {
                "id": label,
                "path": str(path.relative_to(ROOT)),
                "topic": topic,
                "scraped_at": data.get("scraped_at"),
                "page_count": data.get("page_count") or len(data.get("pages", {})),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hub": str(HUB.relative_to(ROOT)),
        "sources": sources,
        "agents_path": "lemdesk/agents/",
        "scripts_path": "lemdesk/scripts/",
    }


def build_agent_brief(knowledge: dict, facts: dict, topology: dict, gordon: dict) -> dict:
    return {
        "brand": "LEMdesk",
        "tagline": "Same desk on any room. Free LAN kit for local models, agent sync, knowledge search, and session handoff.",
        "by": "LEMdev",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hub": str(HUB.relative_to(ROOT)),
        "page_count": knowledge.get("page_count", len(knowledge.get("pages", {}))),
        "topics": knowledge.get("topics", {}),
        "dmr": facts.get("dmr_defaults", {}),
        "cursor": facts.get("cursor_integration", {}),
        "topology_patterns": [p["id"] for p in topology.get("patterns", [])],
        "gordon_local_run": gordon.get("local_alternative", {}),
        "agent_commands": {
            "scrape": "python3 scrape_lemdesk.py --backend auto --workers 8 --max-depth 2 --post-process",
            "check_dmr": "lemdesk/scripts/check_dmr.sh",
            "run_supervisor": "lemdesk/scripts/run_supervisor.sh",
            "auto_pipeline": "python3 bot.py lemdesk-sync",
            "auto_fast": "python3 bot.py lemdesk-sync --fast",
            "search_kb": "python3 lemdesk_brief.py search 'sbx policy'",
            "open_webui": "lemdesk/scripts/run_open_webui.sh",
            "session_handoff": "python3 bot.py lemdesk-handoff",
            "mcp_server": "lemdesk_mcp_server.py — see lemdesk/mcp/cursor_mcp.json.example",
            "birdseed_with_local_model": (
                "Cursor: Override OpenAI Base URL http://localhost:12434/engines/v1, model ai/glm-4.7-flash"
            ),
        },
        "rag": {
            "docs_dir": str(RAG_DOCS_DIR.relative_to(ROOT)),
            "index_meta": str(RAG_INDEX_META.relative_to(ROOT)),
        },
        "sync": {
            "agents_sync": "https://github.com/CognitiveSand/agents_sync",
            "cursor_paths": "~/.cursor/agents, skills, rules, commands, mcp.json",
            "repo_agents": "lemdesk/agents/",
        },
    }


def write_agent_context_md(brief: dict, topology: dict, facts: dict) -> str:
    lines = [
        "# LEMdesk — agent context",
        "",
        f"Generated: {brief.get('generated_at')}",
        "",
        "## Hub layout",
        "",
        "- `lemdesk/incoming/` — scrape staging",
        "- `lemdesk/data/` — knowledge + facts",
        "- `lemdesk/agents/` — Docker Agent YAML",
        "- `lemdesk/scripts/` — LAN tooling",
        "- `lemdesk/logs/` — briefs and index",
        "",
        "## Point Cursor at LAN Model Runner",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        f"| OpenAI API Key | `{facts.get('cursor_integration', {}).get('openai_api_key', 'not-needed')}` |",
        f"| Override OpenAI Base URL (local) | `{facts.get('dmr_defaults', {}).get('openai_compatible_base')}` |",
        f"| Override OpenAI Base URL (LAN client) | `http://<server-ip>:12434/engines/v1` |",
        "",
        "## Topology decision tree",
        "",
    ]
    for p in topology.get("patterns", []):
        lines.append(f"### {p['name']}")
        lines.append(f"- **When:** {p['when_it_wins']}")
        lines.append(f"- **Config:** {json.dumps(p.get('key_config', {}), indent=0)}")
        lines.append("")

    lines.extend(
        [
            "## Session continuity (honest limits)",
            "",
            "- **Models:** shared DMR URL or per-desktop localhost",
            "- **Agents/skills/MCP:** agents_sync + `lemdesk/agents/` in Git",
            "- **Project:** this repo + generated briefs",
            "- **Chat history:** not native — use Open WebUI or cursor-sync extensions",
            "",
            "## Commands",
            "",
        ]
    )
    for k, v in brief.get("agent_commands", {}).items():
        lines.append(f"- `{k}`: {v}")

    lines.extend(
        [
            "",
            "## Sandboxes + DMR",
            "",
            topology.get("sandbox_network_note", ""),
            "",
            "## Re-scrape",
            "",
            "```bash",
            "python3 scrape_lemdesk.py --backend auto --workers 8 --max-depth 2 --post-process",
            "```",
            "",
            "## Local KB search (no docker agent)",
            "",
            "```bash",
            "python3 lemdesk_brief.py search 'model runner cursor'",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _git_info() -> tuple[str, str]:
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        b = branch.stdout.strip() if branch.returncode == 0 else "unknown"
        c = commit.stdout.strip() if commit.returncode == 0 else "unknown"
        return b, c
    except OSError:
        return "unknown", "unknown"


def write_session_handoff(
    focus: str = "",
    notes: str = "",
    next_steps: str = "",
) -> Path:
    """Generate session_handoff.md from template for cross-room continuity."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    template = HANDOFF_TEMPLATE.read_text() if HANDOFF_TEMPLATE.exists() else "# Session handoff\n"
    branch, commit = _git_info()
    generated = datetime.now(timezone.utc).isoformat()

    default_focus = focus or (
        "LEMdesk — local LAN models, knowledge auto-refresh, agents_sync, Super App index."
    )
    default_next = next_steps or (
        "- `./lemdesk/scripts/check_dmr.sh`\n"
        "- `python3 bot.py lemdesk-review`\n"
        "- Read `lemdesk/logs/lemdesk_agent_context.md`"
    )
    default_notes = notes or "(Add open threads before switching rooms.)"

    body = (
        template.replace("{{generated_at}}", generated)
        .replace("{{git_branch}}", branch)
        .replace("{{git_commit}}", commit)
        .replace("{{workspace}}", str(ROOT))
        .replace("{{focus}}", default_focus)
        .replace("{{next_steps}}", default_next)
        .replace("{{notes}}", default_notes)
    )
    SESSION_HANDOFF.write_text(body)
    return SESSION_HANDOFF


def post_process_all(knowledge: dict | None = None) -> dict:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    k = knowledge or load_knowledge()
    facts = extract_setup_facts(k)
    topology = build_topology_comparison()
    gordon = build_gordon_playbook(k)

    SETUP_FACTS.write_text(json.dumps(facts, indent=2))
    TOPOLOGY.write_text(json.dumps(topology, indent=2))
    GORDON_PLAYBOOK.write_text(json.dumps(gordon, indent=2))
    rag_meta = export_rag_corpus(k)

    brief = build_agent_brief(k, facts, topology, gordon)
    brief["rag_doc_count"] = rag_meta.get("doc_count", 0)
    AGENT_BRIEF.write_text(json.dumps(brief, indent=2))
    AGENT_CONTEXT.write_text(write_agent_context_md(brief, topology, facts))
    SUPER_APP_INDEX.write_text(json.dumps(build_super_app_index(), indent=2))
    if not SESSION_HANDOFF.exists():
        write_session_handoff()

    return {
        "setup_facts": str(SETUP_FACTS),
        "topology": str(TOPOLOGY),
        "gordon_playbook": str(GORDON_PLAYBOOK),
        "rag_docs": str(RAG_DOCS_DIR),
        "rag_index_meta": str(RAG_INDEX_META),
        "agent_brief": str(AGENT_BRIEF),
        "agent_context": str(AGENT_CONTEXT),
        "super_app_index": str(SUPER_APP_INDEX),
        "session_handoff": str(SESSION_HANDOFF),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        q = " ".join(sys.argv[2:])
        hits = search_knowledge(q)
        if not hits:
            print("No matches.")
            raise SystemExit(1)
        for h in hits:
            print(f"[{h['score']}] {h['title']} ({h['topic']})")
            print(f"  {h['url']}")
            print(f"  {h['snippet'][:200]}...")
        raise SystemExit(0)

    paths = post_process_all()
    for k, v in paths.items():
        print(f"{k} → {v}")
