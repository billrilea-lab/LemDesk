"""Desk Health — score your LEMdesk setup for demo and diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
LEMDESK = ROOT / "lemdesk"
DATA = LEMDESK / "data"
LOGS = LEMDESK / "logs"
DMR_PORT = int(os.environ.get("DMR_PORT", "12434"))
DMR_URL = f"http://localhost:{DMR_PORT}/engines/v1/models"


def _git_info() -> tuple[str, str]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return branch, commit
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", "unknown"


def _file_age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 3600


def _check_dmr() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        r = httpx.get(DMR_URL, timeout=5.0)
        latency_ms = round((time.perf_counter() - start) * 1000)
        if r.status_code == 200:
            data = r.json()
            models = data.get("data") or data.get("models") or []
            if isinstance(models, dict):
                models = list(models.keys())
            count = len(models) if isinstance(models, list) else 0
            return {
                "id": "dmr",
                "label": "Docker Model Runner",
                "status": "ok",
                "score": 25,
                "detail": f"{count} model(s) on :{DMR_PORT} ({latency_ms}ms)",
                "models": models[:6] if isinstance(models, list) else [],
            }
        return {
            "id": "dmr",
            "label": "Docker Model Runner",
            "status": "warn",
            "score": 8,
            "detail": f"HTTP {r.status_code} on :{DMR_PORT}",
        }
    except Exception as exc:
        return {
            "id": "dmr",
            "label": "Docker Model Runner",
            "status": "fail",
            "score": 0,
            "detail": f"Unreachable on :{DMR_PORT} — {exc.__class__.__name__}",
        }


def _check_knowledge() -> dict[str, Any]:
    path = DATA / "knowledge.json"
    if not path.exists():
        return {
            "id": "knowledge",
            "label": "Knowledge corpus",
            "status": "fail",
            "score": 0,
            "detail": "Missing lemdesk/data/knowledge.json — run lemdesk-sync",
        }
    try:
        k = json.loads(path.read_text())
        pages = len(k.get("pages") or {})
    except json.JSONDecodeError:
        pages = 0
    age_h = _file_age_hours(path) or 999
    if pages >= 50 and age_h < 168:
        score, status = 20, "ok"
    elif pages >= 10:
        score, status = 12, "warn"
    else:
        score, status = 5, "warn"
    detail = f"{pages} pages · updated {age_h:.0f}h ago"
    return {
        "id": "knowledge",
        "label": "Knowledge corpus",
        "status": status,
        "score": score,
        "detail": detail,
        "page_count": pages,
        "age_hours": round(age_h, 1),
    }


def _check_rag() -> dict[str, Any]:
    meta_path = DATA / "rag_index_meta.json"
    docs_dir = DATA / "rag_docs"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            count = meta.get("doc_count") or len(list(docs_dir.glob("*.md")))
        except json.JSONDecodeError:
            count = len(list(docs_dir.glob("*.md")))
    else:
        count = len(list(docs_dir.glob("*.md"))) if docs_dir.exists() else 0
    if count >= 40:
        return {
            "id": "rag",
            "label": "RAG index",
            "status": "ok",
            "score": 15,
            "detail": f"{count} markdown docs indexed",
            "doc_count": count,
        }
    if count > 0:
        return {
            "id": "rag",
            "label": "RAG index",
            "status": "warn",
            "score": 8,
            "detail": f"{count} docs — run lemdesk-sync for full corpus",
            "doc_count": count,
        }
    return {
        "id": "rag",
        "label": "RAG index",
        "status": "fail",
        "score": 0,
        "detail": "No RAG docs — run lemdesk-sync",
        "doc_count": 0,
    }


def _check_handoff() -> dict[str, Any]:
    path = LOGS / "session_handoff.md"
    if not path.exists():
        return {
            "id": "handoff",
            "label": "Session handoff",
            "status": "warn",
            "score": 5,
            "detail": "No handoff yet — run lemdesk-smart-handoff before switching rooms",
        }
    age_h = _file_age_hours(path) or 999
    score = 15 if age_h < 72 else 8
    status = "ok" if age_h < 72 else "warn"
    return {
        "id": "handoff",
        "label": "Session handoff",
        "status": status,
        "score": score,
        "detail": f"Updated {age_h:.0f}h ago",
        "path": str(path),
    }


def _check_mcp() -> dict[str, Any]:
    mcp = ROOT / "lemdesk_mcp_server.py"
    if mcp.exists():
        return {
            "id": "mcp",
            "label": "MCP server",
            "status": "ok",
            "score": 15,
            "detail": "lemdesk_mcp_server.py ready for Cursor",
        }
    return {
        "id": "mcp",
        "label": "MCP server",
        "status": "fail",
        "score": 0,
        "detail": "Missing lemdesk_mcp_server.py",
    }


def _check_incoming() -> dict[str, Any]:
    incoming = LEMDESK / "incoming"
    if not incoming.exists():
        return {
            "id": "incoming",
            "label": "Agent sync inbox",
            "status": "ok",
            "score": 10,
            "detail": "No pending sync files",
            "pending": 0,
        }
    pending = len(list(incoming.glob("*.json")))
    if pending == 0:
        return {
            "id": "incoming",
            "label": "Agent sync inbox",
            "status": "ok",
            "score": 10,
            "detail": "Inbox clear",
            "pending": 0,
        }
    # Scrape staging files are normal when corpus is fresh — don't dock the score.
    k_path = DATA / "knowledge.json"
    age_h = _file_age_hours(k_path) if k_path.exists() else 999
    if age_h < 168:
        return {
            "id": "incoming",
            "label": "Scrape staging",
            "status": "ok",
            "score": 10,
            "detail": f"{pending} staging file(s) — corpus fresh ({age_h:.0f}h ago)",
            "pending": pending,
        }
    return {
        "id": "incoming",
        "label": "Agent sync inbox",
        "status": "warn",
        "score": 5,
        "detail": f"{pending} file(s) waiting — run lemdesk-sync",
        "pending": pending,
    }


def run_health_check() -> dict[str, Any]:
    """Return structured health report with 0–100 score."""
    checks = [
        _check_dmr(),
        _check_knowledge(),
        _check_rag(),
        _check_handoff(),
        _check_mcp(),
        _check_incoming(),
    ]
    raw = sum(c["score"] for c in checks)
    score = min(100, raw)
    branch, commit = _git_info()

    if score >= 85:
        grade = "A"
        summary = "Desk is production-ready — models, corpus, and handoff are wired."
    elif score >= 65:
        grade = "B"
        summary = "Desk is healthy — a quick sync will tighten things up."
    elif score >= 40:
        grade = "C"
        summary = "Partial setup — run lemdesk-sync and check DMR."
    else:
        grade = "D"
        summary = "Desk needs setup — start with lemdesk-sync and check_dmr.sh."

    return {
        "product": "LEMdesk Pro",
        "version": "0.1.0-demo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "grade": grade,
        "summary": summary,
        "workspace": str(ROOT),
        "git_branch": branch,
        "git_commit": commit,
        "checks": checks,
        "commands": {
            "desk_up": "python3 bot.py lemdesk-desk-up",
            "sync": "python3 bot.py lemdesk-sync --fast",
            "smart_handoff": "python3 bot.py lemdesk-smart-handoff",
            "health": "python3 bot.py lemdesk-health",
            "pro_menubar": "python3 bot.py lemdesk-pro",
        },
    }
