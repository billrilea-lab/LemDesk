"""CLI entry: python3 -m lemdesk_pro [health|smart-handoff|menubar]"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="LEMdesk Pro — desk health, smart handoff, menu bar")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("health", help="Print desk health score")
    h.add_argument("--json", action="store_true")

    sh = sub.add_parser("smart-handoff", help="Write desk pack + agent prompt")
    sh.add_argument("--focus", default="")
    sh.add_argument("--notes", default="")
    sh.add_argument("--next-steps", default="")

    du = sub.add_parser("desk-up", help="Morning startup: Docker, DMR, mounts")
    du.add_argument("--sync", action="store_true")
    du.add_argument("--mount-nas", action="store_true")
    du.add_argument("--json", action="store_true")

    mb = sub.add_parser("menubar", help="Menu bar app + dashboard")
    mb.add_argument("--port", type=int, default=8765)
    mb.add_argument("--cli", action="store_true", help="Headless dashboard only")

    args = p.parse_args()

    if args.cmd == "health":
        from lemdesk_pro.desk_health import run_health_check

        report = run_health_check()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Desk Health: {report['score']}/100 ({report['grade']})")
            print(report["summary"])
            for c in report["checks"]:
                icon = {"ok": "✓", "warn": "!", "fail": "✗"}.get(c["status"], "?")
                print(f"  [{icon}] {c['label']}: {c['detail']}")
        return 0 if report["score"] >= 40 else 1

    if args.cmd == "smart-handoff":
        from lemdesk_pro.smart_handoff import write_smart_handoff

        paths = write_smart_handoff(
            focus=args.focus,
            notes=args.notes,
            next_steps=args.next_steps,
        )
        for label, path in paths.items():
            print(f"{label}: {path}")
        return 0

    if args.cmd == "desk-up":
        from lemdesk_pro.desk_up import run_desk_up

        print("=== LEMdesk Desk Up ===")
        report = run_desk_up(sync=args.sync, open_nas=args.mount_nas)
        if args.json:
            print(json.dumps(report, indent=2))
        health = report.get("health") or {}
        return 0 if health.get("score", 0) >= 40 else 1

    if args.cmd == "menubar":
        from lemdesk_pro.menubar import run_cli_fallback, run_menubar

        if args.cli:
            run_cli_fallback(port=args.port)
        else:
            run_menubar(port=args.port)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
