"""MCP server — search LEMdesk knowledge base from Cursor / Claude.

Add to ~/.cursor/mcp.json (see lemdesk/mcp/cursor_mcp.json.example):

  "lemdesk-kb": {
    "command": "python3",
    "args": ["/full/path/to/lemdesk_mcp_server.py"]
  }
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lemdesk_brief import load_knowledge, search_knowledge

mcp = FastMCP(
    "lemdesk-kb",
    instructions=(
        "Search LEMdesk local knowledge: Model Runner setup, sandboxes, agents, MCP. "
        "Corpus lives in lemdesk/data/knowledge.json."
    ),
)

HUB = Path(__file__).parent / "lemdesk"


@mcp.tool()
def search_lemdesk_docs(query: str, limit: int = 8) -> str:
    """Search the local LEMdesk knowledge base by keywords.

    Args:
        query: Search terms (e.g. 'sbx policy', 'cursor model runner')
        limit: Max results (default 8)
    """
    hits = search_knowledge(query, limit=max(1, min(limit, 20)))
    if not hits:
        return f"No matches for: {query!r}. Run: python3 bot.py lemdesk-review"
    return json.dumps(hits, indent=2)


@mcp.tool()
def get_lemdesk_handoff() -> str:
    """Return session handoff markdown for continuing work across rooms/desktops."""
    path = HUB / "logs" / "session_handoff.md"
    if not path.exists():
        return (
            "No handoff file yet. Run: python3 bot.py lemdesk-handoff\n"
            "Then open lemdesk/logs/session_handoff.md"
        )
    return path.read_text()


@mcp.tool()
def get_lemdesk_setup_facts() -> str:
    """Return extracted DMR ports, URLs, models, and Cursor integration settings."""
    facts_path = HUB / "data" / "setup_facts.json"
    if not facts_path.exists():
        return "Missing setup_facts.json — run: python3 bot.py lemdesk-review"
    return facts_path.read_text()


@mcp.tool()
def list_lemdesk_topics() -> str:
    """List topic counts from the LEMdesk knowledge corpus."""
    k = load_knowledge()
    topics = k.get("topics") or {}
    if not topics:
        pages = k.get("pages", {})
        topics = {}
        for p in pages.values():
            t = p.get("topic", "general")
            topics[t] = topics.get(t, 0) + 1
    return json.dumps(
        {
            "page_count": k.get("page_count", len(k.get("pages", {}))),
            "scraped_at": k.get("scraped_at"),
            "topics": topics,
        },
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
