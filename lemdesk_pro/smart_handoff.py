"""Smart Handoff — structured desk pack for cross-room agent continuity."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lemdesk_brief import (
    AGENT_BRIEF,
    AGENT_CONTEXT,
    DATA_DIR,
    KNOWLEDGE_PATH,
    SESSION_HANDOFF,
    SETUP_FACTS,
    load_knowledge,
    write_session_handoff,
)
from lemdesk_pro.desk_health import run_health_check

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "lemdesk" / "logs"
DESK_PACK = LOGS / "desk_pack.json"
DESK_PROMPT = LOGS / "desk_handoff_prompt.md"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _infer_focus() -> str:
    brief = _load_json(AGENT_BRIEF)
    topics = brief.get("top_topics") or brief.get("topics") or []
    if isinstance(topics, dict):
        topics = list(topics.values())
    if topics:
        names = [
            (t.get("title") or t.get("name") or str(t)) if isinstance(t, dict) else str(t)
            for t in list(topics)[:3]
        ]
        return f"LEMdesk — {', '.join(names)}"
    k = load_knowledge()
    pages = k.get("pages") or {}
    if pages:
        return f"LEMdesk — {len(pages)}-page knowledge corpus, local models + agent sync"
    return "LEMdesk — local LAN desk, models, and agent continuity"


def _build_suggested_prompt(pack: dict[str, Any]) -> str:
    health = pack.get("health") or {}
    session = pack.get("session") or {}
    workspace = pack.get("workspace") or {}
    rag = pack.get("rag") or {}

    lines = [
        "# LEMdesk Smart Handoff",
        "",
        f"> Paste this into Cursor (or any agent) when you open a new room/desktop.",
        "",
        "## Context",
        "",
        session.get("focus") or "Continuing LEMdesk work.",
        "",
        "## Workspace",
        "",
        f"- **Path:** `{workspace.get('path', '')}`",
        f"- **Git:** `{workspace.get('branch', '?')}` @ `{workspace.get('commit', '?')}`",
        f"- **Desk Health:** {health.get('score', '?')}/100 ({health.get('grade', '?')})",
        "",
        "## What to read first",
        "",
        "1. `lemdesk/logs/session_handoff.md`",
        "2. `lemdesk/logs/lemdesk_agent_context.md`",
        "3. MCP tool `get_lemdesk_handoff` if configured",
        "",
        "## Active stack",
        "",
    ]
    models = (pack.get("models") or {}).get("known") or []
    if models:
        for m in models[:5]:
            lines.append(f"- Model: `{m}`")
    else:
        lines.append("- Local models via Docker Model Runner (:12434)")
    lines.extend(
        [
            f"- RAG corpus: **{rag.get('doc_count', 0)}** docs",
            "",
            "## Next steps",
            "",
            session.get("next_steps") or "- Run `python3 bot.py lemdesk-health`",
            "",
            "## Notes",
            "",
            session.get("notes") or "(none)",
            "",
            "---",
            f"*Generated {pack.get('generated_at', '')} by LEMdesk Pro Smart Handoff*",
        ]
    )
    return "\n".join(lines)


def build_desk_pack(
    focus: str = "",
    notes: str = "",
    next_steps: str = "",
) -> dict[str, Any]:
    """Build structured desk pack JSON + markdown artifacts."""
    health = run_health_check()
    facts = _load_json(SETUP_FACTS)
    brief = _load_json(AGENT_BRIEF)
    rag_meta = _load_json(DATA_DIR / "rag_index_meta.json")

    default_next = next_steps or (
        "- `python3 bot.py lemdesk-health`\n"
        "- Read `lemdesk/logs/lemdesk_agent_context.md`\n"
        "- `./lemdesk/scripts/check_dmr.sh`"
    )

    pack: dict[str, Any] = {
        "schema": "deskspec/1.0",
        "product": "LEMdesk Pro",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session": {
            "focus": focus or _infer_focus(),
            "notes": notes or "",
            "next_steps": default_next,
        },
        "workspace": {
            "path": str(ROOT),
            "branch": health.get("git_branch"),
            "commit": health.get("git_commit"),
        },
        "health": {
            "score": health.get("score"),
            "grade": health.get("grade"),
            "summary": health.get("summary"),
            "checks": health.get("checks"),
        },
        "rag": {
            "doc_count": rag_meta.get("doc_count") or len(list((DATA_DIR / "rag_docs").glob("*.md"))),
            "knowledge_pages": len((load_knowledge().get("pages") or {})),
            "knowledge_path": str(KNOWLEDGE_PATH),
        },
        "models": {
            "dmr_port": facts.get("dmr_port") or 12434,
            "known": facts.get("models") or brief.get("models") or [],
            "base_urls": facts.get("base_urls") or [],
        },
        "artifacts": {
            "session_handoff": str(SESSION_HANDOFF),
            "agent_context": str(AGENT_CONTEXT),
            "agent_brief": str(AGENT_BRIEF),
        },
        "commands": health.get("commands") or {},
    }

    pack["suggested_prompt"] = _build_suggested_prompt(pack)
    return pack


def write_smart_handoff(
    focus: str = "",
    notes: str = "",
    next_steps: str = "",
) -> dict[str, Path]:
    """Write desk pack, prompt, and refresh session handoff."""
    LOGS.mkdir(parents=True, exist_ok=True)
    pack = build_desk_pack(focus=focus, notes=notes, next_steps=next_steps)

    write_session_handoff(
        focus=pack["session"]["focus"],
        notes=pack["session"]["notes"] or "(Add open threads before switching rooms.)",
        next_steps=pack["session"]["next_steps"],
    )

    DESK_PACK.write_text(json.dumps(pack, indent=2))
    DESK_PROMPT.write_text(pack["suggested_prompt"])

    return {
        "desk_pack": DESK_PACK,
        "desk_prompt": DESK_PROMPT,
        "session_handoff": SESSION_HANDOFF,
    }
