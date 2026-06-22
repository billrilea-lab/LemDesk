#!/usr/bin/env python3
"""AI Path Assistant — wizard, doctor, resolve paths across Mac/Windows/Synology."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lemdesk.path_registry import (  # noqa: E402
    _user_config_dir,
    assistant_prompt,
    doctor,
    export_env,
    load_config,
    resolve_logical,
    sanitize_config,
    sanitize_user_path,
    TEMPLATE,
    validate_config,
)

try:
    import yaml
except ImportError:
    yaml = None


def _write_config(data: dict) -> Path:
    dest = _user_config_dir() / "ai_paths.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        raise SystemExit("pip install pyyaml")
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    dest.write_text(yaml.dump(clean, default_flow_style=False, sort_keys=False))
    return dest


def _prompt_path(label: str, default: str, hint: str = "") -> str:
    """Ask until we get a plausible path or user presses Enter for default."""
    print(label)
    if hint:
        print(hint)
    for attempt in range(3):
        raw = input("> ").strip()
        if not raw:
            print(f"  → using default: {default}")
            return default
        path, err = sanitize_user_path(raw, default, label)
        if err:
            print(f"  ✗ {err}")
            if attempt < 2:
                print("  Try again (or press Enter for default):")
            continue
        print(f"  ✓ {path}")
        return path
    print(f"  → too many tries — using default: {default}")
    return default


def cmd_wizard(_: argparse.Namespace) -> int:
    if yaml is None:
        print("Install PyYAML: python3 -m pip install pyyaml")
        return 1

    host = socket.gethostname().split(".")[0]
    is_win = platform.system() == "Windows"
    home = Path.home()

    print("=== LEMdesk AI Path Wizard ===\n")
    print(f"Machine: {host} ({platform.system()})")
    print("Enter folder paths only — not shell commands.\n")

    base = yaml.safe_load(TEMPLATE.read_text()) if TEMPLATE.exists() else {}
    machines = base.get("machines") or {}

    default_nas = "/Volumes/docker-1/AI" if not is_win else "Z:/AI"
    synology = _prompt_path(
        "NAS / Synology AI folder path",
        default_nas,
        "  Mac: /Volumes/docker-1/AI\n"
        "  Win: Z:/AI\n"
        "  Mount SMB in Finder first — don't paste smb:// here",
    )
    local_fast = _prompt_path(
        "Local fast cache",
        str(home / "AI-Local"),
    )
    projects = _prompt_path(
        "Projects / workspace root",
        str(home / "Cursor- Crypto"),
    )

    machines[host] = {
        "os": "windows" if is_win else "darwin",
        "volumes": {
            "synology": synology,
            "local_fast": local_fast,
        },
    }
    base["machine"] = "auto"
    base["machines"] = machines

    if "projects" in (base.get("logical") or {}):
        base["logical"]["projects"]["paths"] = [projects, "{volume:synology}/dev"]

    dest = _write_config(base)
    print(f"\nWrote {dest}")
    print("Run: python3 bot.py ai-paths doctor")
    return 0


def cmd_repair(_: argparse.Namespace) -> int:
    if yaml is None:
        print("pip install pyyaml")
        return 1
    dest = _user_config_dir() / "ai_paths.yaml"
    if dest.exists():
        bak = dest.with_suffix(f".yaml.bak.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(dest, bak)
        print(f"Backed up → {bak}")

    old = yaml.safe_load(dest.read_text()) if dest.exists() else {}
    base = yaml.safe_load(TEMPLATE.read_text()) if TEMPLATE.exists() else {}
    home = Path.home()
    defaults = {
        "synology": "/Volumes/docker-1/AI",
        "local_fast": str(home / "AI-Local"),
        "projects": str(home / "Cursor- Crypto"),
    }
    # Preserve valid machine volumes from old config
    host = socket.gethostname().split(".")[0]
    old_vols = ((old.get("machines") or {}).get(host) or {}).get("volumes") or {}
    for k, v in old_vols.items():
        _, err = sanitize_user_path(str(v), defaults.get(k, ""), k)
        if not err:
            defaults[k] = str(v)

    fixed = sanitize_config({**base, **{k: v for k, v in old.items() if k in ("machines", "logical")}}, defaults)
    fixed["machine"] = "auto"
    if host not in (fixed.get("machines") or {}):
        fixed.setdefault("machines", {})[host] = {
            "os": "windows" if platform.system() == "Windows" else "darwin",
            "volumes": {"synology": defaults["synology"], "local_fast": defaults["local_fast"]},
        }
    _write_config(fixed)
    print(f"Repaired → {dest}")
    warnings = validate_config(fixed)
    if warnings:
        print("Remaining issues:", warnings)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor(project_root=Path(args.project) if args.project else ROOT)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["score"] >= 50 and not report.get("config_warnings") else 1
    print(f"AI Path Health: {report['score']}/100")
    print(f"Host: {report['hostname']} · Config: {report['config']}\n")
    if report.get("config_warnings"):
        print("Config errors (run: python3 bot.py ai-paths repair):")
        for w in report["config_warnings"]:
            print(f"  ✗ {w}")
        print()
    if report["missing_volumes"]:
        print("Missing volumes:")
        for v in report["missing_volumes"]:
            print(f"  [{v['volume']}] {v['path']}")
        print()
    for name, info in sorted(report["paths"].items()):
        icon = "ok" if info["exists"] else "!!"
        print(f"  [{icon}] {name:12} {info['resolved']}")
    if report["issues"]:
        print(f"\n{len(report['issues'])} path(s) need attention — mount NAS or run wizard")
    return 0 if report["score"] >= 50 and not report.get("config_warnings") else 1


def cmd_resolve(args: argparse.Namespace) -> int:
    p = resolve_logical(args.name, project_root=Path(args.project) if args.project else ROOT)
    if not p:
        print(f"Unknown logical path: {args.name}")
        return 1
    print(p)
    return 0 if p.exists() else 2


def cmd_export(args: argparse.Namespace) -> int:
    text = export_env(project_root=Path(args.project) if args.project else ROOT)
    if args.out:
        Path(args.out).write_text(text)
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    text = assistant_prompt(project_root=Path(args.project) if args.project else ROOT)
    out = Path(args.out) if args.out else ROOT / "lemdesk" / "logs" / "ai_path_map.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text)
    print(f"\n→ {out}")
    return 0


def cmd_init(_: argparse.Namespace) -> int:
    dest = _user_config_dir() / "ai_paths.yaml"
    if dest.exists():
        print(f"Config already exists: {dest}")
        return 0
    if yaml is None:
        print("pip install pyyaml")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(TEMPLATE.read_text())
    print(f"Copied template → {dest}")
    print("Edit paths, then: python3 lemdesk/scripts/ai_path_assistant.py wizard")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="LEMdesk AI Path Assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("wizard", help="Interactive setup for this machine").set_defaults(func=cmd_wizard)
    sub.add_parser("init", help="Copy template to ~/.config/lemdesk/ai_paths.yaml").set_defaults(func=cmd_init)
    sub.add_parser("repair", help="Fix corrupt config (bad wizard paste, etc.)").set_defaults(func=cmd_repair)

    d = sub.add_parser("doctor", help="Check all logical paths exist")
    d.add_argument("--json", action="store_true")
    d.add_argument("--project", default="")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("resolve", help="Print resolved path for one logical name")
    r.add_argument("name", help="e.g. skills, rag, secrets, synology via volume")
    r.add_argument("--project", default="")
    r.set_defaults(func=cmd_resolve)

    e = sub.add_parser("export", help="Print shell exports LEMDESK_*")
    e.add_argument("--out", default="")
    e.add_argument("--project", default="")
    e.set_defaults(func=cmd_export)

    b = sub.add_parser("brief", help="Write ai_path_map.md for Cursor handoff")
    b.add_argument("--out", default="")
    b.add_argument("--project", default="")
    b.set_defaults(func=cmd_brief)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
