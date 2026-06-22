"""Cross-platform AI path registry — Synology, multi-drive, Mac + Windows."""

from __future__ import annotations

import json
import os
import platform
import re
import socket
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
HUB = Path(__file__).resolve().parent
TEMPLATE = HUB / "config" / "ai_paths.template.yaml"

TOKEN_RE = re.compile(r"\{(\w+)(?::(\w+))?\}")

# End users paste commands, URLs, comments — reject early
_PATH_REJECT = re.compile(
    r"(python\d*|bot\.py|pip3?|curl|wget|sudo|&&|\||;|\$\(|`|\n|\r|# →|#->)",
    re.I,
)
_WIN_PATH = re.compile(r"^[A-Za-z]:[/\\]")
_UNC_PATH = re.compile(r"^//[^/]+/")


def sanitize_user_path(raw: str, default: str, field: str = "path") -> tuple[str, str | None]:
    """Return (clean_path, error_message). Takes first line only."""
    if not raw or not raw.strip():
        return default, None
    s = raw.strip().splitlines()[0].strip()
    if s.startswith("#"):
        return default, f"{field}: looks like a comment, not a path"
    if s.lower().startswith(("http://", "https://")):
        return default, f"{field}: use a folder path, not a web URL"
    if s.lower().startswith("smb://"):
        return default, (
            f"{field}: mount SMB in Finder first (Cmd+K), then enter the /Volumes/... path"
        )
    if _PATH_REJECT.search(s):
        return default, f"{field}: that looks like a command, not a folder path"
    if not (
        s.startswith("/")
        or s.startswith("~")
        or s.startswith("./")
        or _WIN_PATH.match(s)
        or _UNC_PATH.match(s)
        or "{" in s  # template token
    ):
        return default, f"{field}: path must start with /, ~, C:/, Z:/, or //"
    return os.path.expanduser(s), None


def validate_config(cfg: dict[str, Any]) -> list[str]:
    """Human-readable config problems (corrupt wizard input, etc.)."""
    warnings: list[str] = []
    host = _hostname()
    machines = cfg.get("machines") or {}
    prof = machines.get(host) or {}
    for vol, path in (prof.get("volumes") or {}).items():
        if isinstance(path, str):
            _, err = sanitize_user_path(path, "", f"machines.{host}.volumes.{vol}")
            if err:
                warnings.append(err)
    for name, spec in (cfg.get("logical") or {}).items():
        for i, p in enumerate(spec.get("paths") or []):
            if "{" in str(p):
                continue
            _, err = sanitize_user_path(str(p), "", f"logical.{name}.paths[{i}]")
            if err:
                warnings.append(err)
    return warnings


def sanitize_config(cfg: dict[str, Any], defaults: dict[str, str] | None = None) -> dict[str, Any]:
    """Drop corrupt paths; fill machine volumes from defaults."""
    defaults = defaults or {}
    out = json.loads(json.dumps(cfg))  # deep copy
    host = _hostname()
    machines = out.setdefault("machines", {})
    prof = machines.setdefault(host, {"os": "darwin", "volumes": {}})
    vols = prof.setdefault("volumes", {})
    for key in ("synology", "local_fast"):
        if key in vols:
            clean, err = sanitize_user_path(vols[key], defaults.get(key, vols[key]), key)
            if err:
                vols[key] = defaults.get(key, clean)
    logical = out.get("logical") or {}
    if "projects" in logical:
        paths = logical["projects"].get("paths") or []
        fixed = []
        for p in paths:
            if "{" in str(p):
                fixed.append(p)
                continue
            clean, err = sanitize_user_path(str(p), str(Path.home() / "Projects"), "projects")
            fixed.append(clean if not err else defaults.get("projects", clean))
        logical["projects"]["paths"] = fixed
    return out


def _user_config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(base) / "lemdesk"
    return Path.home() / ".config" / "lemdesk"


def config_paths() -> list[Path]:
    env = os.environ.get("LEMDESK_AI_PATHS")
    if env:
        return [Path(env).expanduser()]
    return [
        _user_config_dir() / "ai_paths.yaml",
        HUB / "config" / "ai_paths.yaml",
        TEMPLATE,
    ]


def load_config() -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    for p in config_paths():
        if p.exists():
            data = yaml.safe_load(p.read_text()) or {}
            data["_config_path"] = str(p)
            return data
    return {"_config_path": str(TEMPLATE)}


def _hostname() -> str:
    return (
        os.environ.get("LEMDESK_MACHINE")
        or os.environ.get("COMPUTERNAME")
        or socket.gethostname().split(".")[0]
    )


def _expand_token(token: str, ctx: dict[str, Any]) -> str:
    if token == "home":
        return str(Path.home())
    if token == "project":
        return str(ctx.get("project_root", ROOT))
    if token == "user":
        return os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if token.startswith("env:"):
        return os.environ.get(token[4:], "")
    return str(ctx.get("volumes", {}).get(token, f"{{{token}}}"))


def _expand_string(s: str, ctx: dict[str, Any]) -> str:
    out = s.replace("%USERNAME%", os.environ.get("USERNAME", os.environ.get("USER", "")))

    def repl(m: re.Match[str]) -> str:
        kind, vol = m.group(1), m.group(2)
        if kind == "volume" and vol:
            return _expand_token(vol, ctx)
        return _expand_token(kind, ctx)

    prev = None
    while prev != out:
        prev = out
        out = TOKEN_RE.sub(repl, out)
    return os.path.expanduser(out)


def _machine_profile(cfg: dict[str, Any]) -> dict[str, Any]:
    machines = cfg.get("machines") or {}
    name = cfg.get("machine") or "auto"
    if name == "auto":
        host = _hostname()
        if host in machines:
            return machines[host]
        for key, prof in machines.items():
            if key.lower() == host.lower():
                return prof
        return {}
    return machines.get(name, {})


def build_context(cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> dict[str, Any]:
    c = cfg or load_config()
    profile = _machine_profile(c)
    volumes = dict(c.get("volumes") or {})
    os_key = "windows" if platform.system() == "Windows" else "mac" if platform.system() == "Darwin" else "linux"

    resolved_volumes: dict[str, str] = {}
    for vol_name, vol_def in volumes.items():
        if isinstance(vol_def, str):
            resolved_volumes[vol_name] = _expand_string(vol_def, {"volumes": resolved_volumes, "project_root": project_root or ROOT})
            continue
        override = (profile.get("volumes") or {}).get(vol_name)
        if override:
            clean, err = sanitize_user_path(str(override), "", vol_name)
            if err:
                override = None  # fall back to template default
            else:
                override = clean
        if override:
            resolved_volumes[vol_name] = _expand_string(str(override), {"volumes": resolved_volumes, "project_root": project_root or ROOT})
        elif os_key in vol_def:
            resolved_volumes[vol_name] = _expand_string(str(vol_def[os_key]), {"volumes": resolved_volumes, "project_root": project_root or ROOT})

    return {
        "hostname": _hostname(),
        "os": platform.system(),
        "config_path": c.get("_config_path"),
        "project_root": str(project_root or ROOT),
        "volumes": resolved_volumes,
        "profile": profile,
        "overrides": c.get("overrides") or {},
    }


def resolve_logical(name: str, cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> Path | None:
    c = cfg or load_config()
    ctx = build_context(c, project_root)
    logical = (c.get("logical") or {}).get(name)
    if not logical:
        return None

    paths = logical.get("paths") or []
    primary_idx = (ctx.get("overrides") or {}).get(name, logical.get("primary", 0))

    # Try primary first, then fallbacks in order
    order = [primary_idx] + [i for i in range(len(paths)) if i != primary_idx]
    for idx in order:
        if idx < 0 or idx >= len(paths):
            continue
        raw = _expand_string(str(paths[idx]), ctx)
        p = Path(raw)
        if p.exists():
            return p.resolve()
    # Return expanded primary even if missing (for doctor to report)
    if paths:
        idx = primary_idx if 0 <= primary_idx < len(paths) else 0
        return Path(_expand_string(str(paths[idx]), ctx))
    return None


def resolve_all(cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    c = cfg or load_config()
    ctx = build_context(c, project_root)
    out: dict[str, dict[str, Any]] = {}
    for name, spec in (c.get("logical") or {}).items():
        paths = spec.get("paths") or []
        expanded = [_expand_string(str(p), ctx) for p in paths]
        chosen = resolve_logical(name, c, project_root)
        p = chosen
        out[name] = {
            "description": spec.get("description", ""),
            "resolved": str(p) if p else None,
            "exists": p.exists() if p else False,
            "is_dir": p.is_dir() if p and p.exists() else False,
            "candidates": expanded,
        }
    return out


def doctor(cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> dict[str, Any]:
    c = cfg or load_config()
    ctx = build_context(c, project_root)
    resolved = resolve_all(c, project_root)
    issues: list[dict[str, str]] = []
    ok = 0
    for name, info in resolved.items():
        if info["exists"]:
            ok += 1
        else:
            issues.append({
                "logical": name,
                "expected": info["resolved"] or "?",
                "candidates": info["candidates"],
                "fix": f"Mount volume or run: ai_path_assistant.py wizard",
            })

    missing_volumes = []
    config_warnings = validate_config(c)
    for vol, path in ctx["volumes"].items():
        vp = Path(path)
        if not vp.exists():
            missing_volumes.append({"volume": vol, "path": path})

    score = max(0, min(100, int(100 * ok / max(len(resolved), 1))))
    if config_warnings:
        score = min(score, 50)
    return {
        "hostname": ctx["hostname"],
        "os": ctx["os"],
        "config": ctx["config_path"],
        "volumes": ctx["volumes"],
        "score": score,
        "ok_count": ok,
        "total": len(resolved),
        "paths": resolved,
        "missing_volumes": missing_volumes,
        "config_warnings": config_warnings,
        "issues": issues,
    }


def export_env(cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> str:
    """Shell-exportable LEMDESK_* variables for scripts and agents."""
    resolved = resolve_all(cfg, project_root)
    lines = ["# LEMdesk AI paths — source this file or paste into shell profile"]
    for name, info in sorted(resolved.items()):
        key = f"LEMDESK_{name.upper()}"
        val = info.get("resolved") or ""
        lines.append(f'export {key}="{val}"')
    lines.append(f'export LEMDESK_PROJECT="{project_root or ROOT}"')
    lines.append(f'export LEMDESK_CONFIG="{load_config().get("_config_path", "")}"')
    return "\n".join(lines) + "\n"


def assistant_prompt(cfg: dict[str, Any] | None = None, project_root: Path | None = None) -> str:
    """Markdown brief for pasting into Cursor — where everything lives on this machine."""
    report = doctor(cfg, project_root)
    lines = [
        "# AI Path Map — this machine",
        "",
        f"- **Host:** {report['hostname']} ({report['os']})",
        f"- **Config:** `{report['config']}`",
        f"- **Path health:** {report['score']}/100 ({report['ok_count']}/{report['total']} exist)",
        "",
        "## Volumes",
        "",
    ]
    for vol, path in report["volumes"].items():
        status = "ok" if Path(path).exists() else "MISSING"
        lines.append(f"- `{vol}` → `{path}` [{status}]")
    lines.extend(["", "## Logical paths", ""])
    for name, info in sorted(report["paths"].items()):
        flag = "ok" if info["exists"] else "missing"
        lines.append(f"- **{name}** ({flag}): `{info['resolved']}`")
    if report["issues"]:
        lines.extend(["", "## Fix first", ""])
        for issue in report["issues"][:8]:
            lines.append(f"- **{issue['logical']}**: expected `{issue['expected']}`")
    lines.extend([
        "",
        "## Commands",
        "",
        "```bash",
        "python3 lemdesk/scripts/ai_path_assistant.py doctor",
        "python3 lemdesk/scripts/ai_path_assistant.py resolve rag",
        "python3 lemdesk/scripts/ai_path_assistant.py wizard",
        "```",
    ])
    return "\n".join(lines)
