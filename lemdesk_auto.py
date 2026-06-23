"""One-shot auto pipeline for LEMdesk — scrape, merge, RAG, briefs, handoff.

Fast path (default): extra-seeds only if knowledge.json exists and is fresh.
Full path (--full): httpx-first scrape, no raw HTML, high parallelism.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
HUB = ROOT / "lemdesk"
KNOWLEDGE = HUB / "data" / "knowledge.json"
INCOMING = HUB / "incoming"

# Skip full BFS if corpus refreshed within this many days
FRESH_DAYS = 7


def _log(msg: str) -> None:
    print(msg, flush=True)


def _knowledge_age_days() -> float | None:
    if not KNOWLEDGE.exists():
        return None
    try:
        data = json.loads(KNOWLEDGE.read_text())
        scraped = data.get("scraped_at") or data.get("extra_seeds_at")
        if not scraped:
            return None
        dt = datetime.fromisoformat(scraped.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def cleanup_incoming(knowledge: dict | None = None) -> int:
    """Remove incoming/*.json for URLs present in merged knowledge."""
    if not INCOMING.exists():
        return 0
    if knowledge is None and KNOWLEDGE.exists():
        try:
            knowledge = json.loads(KNOWLEDGE.read_text())
        except json.JSONDecodeError:
            knowledge = {}
    pages = set((knowledge or {}).get("pages", {}).keys())
    if not pages:
        return 0

    from scrape_lemdesk import _url_key

    removed = 0
    for p in INCOMING.glob("*.json"):
        try:
            item = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        url = item.get("url", "")
        if url in pages:
            p.unlink()
            removed += 1
    return removed


def run_scrape(
    full: bool,
    backend: str,
    workers: int,
    max_depth: int,
    save_raw: bool,
) -> dict:
    from scrape_lemdesk import (
        build_knowledge_base,
        build_knowledge_extra,
        DEFAULT_OUT,
    )

    if full:
        _log(f"[auto] Full scrape backend={backend} workers={workers} depth={max_depth}")
        return build_knowledge_base(
            backend=backend,
            max_depth=max_depth,
            workers=workers,
            save_raw=save_raw,
        )

    age = _knowledge_age_days()
    if age is not None and age < FRESH_DAYS:
        _log(f"[auto] Corpus fresh ({age:.1f}d) — extra-seeds only")
        return build_knowledge_extra(
            backend="httpx" if backend == "auto" else backend,
            workers=workers,
            save_raw=save_raw,
        )

    _log(f"[auto] Stale/missing corpus — full scrape")
    return build_knowledge_base(
        backend=backend,
        max_depth=max_depth,
        workers=workers,
        save_raw=save_raw,
    )


def run_auto(
    full: bool = False,
    backend: str = "auto",
    workers: int = 10,
    max_depth: int = 2,
    save_raw: bool = False,
    cleanup: bool = True,
    handoff_focus: str = "",
    skip_dmr_check: bool = False,
) -> dict:
    t0 = time.monotonic()
    results: dict = {"steps": []}

    if not skip_dmr_check:
        check = HUB / "scripts" / "check_dmr.sh"
        if check.exists():
            _log("[auto] DMR probe (non-fatal)...")
            subprocess.run(["bash", str(check)], cwd=ROOT, check=False)

    knowledge = run_scrape(full, backend, workers, max_depth, save_raw)
    KNOWLEDGE.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE.write_text(json.dumps(knowledge, indent=2))
    results["page_count"] = knowledge.get("page_count", len(knowledge.get("pages", {})))
    results["steps"].append("scrape")

    from lemdesk_brief import post_process_all, write_session_handoff

    paths = post_process_all(knowledge)
    results["artifacts"] = paths
    results["steps"].append("post_process")

    if cleanup:
        n = cleanup_incoming(knowledge)
        results["incoming_cleaned"] = n
        results["steps"].append("cleanup_incoming")

    focus = handoff_focus or "LEMdesk auto-refresh — corpus + RAG + briefs updated."
    handoff = write_session_handoff(
        focus=focus,
        next_steps=(
            "- Read lemdesk/logs/session_handoff.md\n"
            "- MCP: lemdesk_mcp_server.py or bot.py lemdesk-search\n"
            "- Supervisor: lemdesk/scripts/run_supervisor.sh"
        ),
    )
    results["session_handoff"] = str(handoff)
    results["steps"].append("handoff")

    try:
        from lemdesk.nas_mirror import mirror_to_nas

        mirror = mirror_to_nas(ROOT)
        results["nas_mirror"] = mirror
        if mirror.get("ok"):
            results["steps"].append("nas_mirror")
    except Exception as exc:
        results["nas_mirror"] = {"ok": False, "error": str(exc)}

    elapsed = time.monotonic() - t0
    results["elapsed_sec"] = round(elapsed, 1)
    results["generated_at"] = datetime.now(timezone.utc).isoformat()

    meta_path = HUB / "logs" / "auto_run.json"
    meta_path.write_text(json.dumps(results, indent=2))
    results["meta_path"] = str(meta_path)

    _log(f"[auto] Done in {elapsed:.1f}s — {results['page_count']} pages")
    _log(f"[auto] Meta → {meta_path}")
    return results


def main() -> int:
    p = argparse.ArgumentParser(description="LEMdesk auto pipeline")
    p.add_argument("--full", action="store_true", help="Force full BFS scrape (not just extra-seeds)")
    p.add_argument("--backend", default="auto", choices=["auto", "httpx", "crawl4ai"])
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--raw", action="store_true", help="Save raw HTML (slower)")
    p.add_argument("--no-cleanup", action="store_true", help="Keep incoming/*.json after merge")
    p.add_argument("--fast", action="store_true", help="httpx, 12 workers, depth 1, skip DMR check")
    p.add_argument("--skip-dmr-check", action="store_true")
    p.add_argument("--focus", default="", help="Session handoff focus line")
    args = p.parse_args()

    skip_dmr = args.skip_dmr_check or args.fast
    workers = args.workers
    max_depth = args.max_depth
    backend = args.backend
    full = args.full
    if args.fast:
        full = True
        backend = "httpx"
        workers = 12
        max_depth = 1

    results = run_auto(
        full=full,
        backend=backend,
        workers=workers,
        max_depth=max_depth,
        save_raw=args.raw,
        cleanup=not args.no_cleanup,
        handoff_focus=args.focus,
        skip_dmr_check=skip_dmr,
    )
    return 0 if results.get("page_count", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
