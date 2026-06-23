"""Mirror LEMdesk corpus + handoff to NAS canonical paths."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = Path(__file__).resolve().parent


def _nas_ai_root() -> Path | None:
    try:
        from lemdesk.path_registry import discover_nas_ai

        p = discover_nas_ai()
        return p if p and p.is_dir() else None
    except Exception:
        return None


def mirror_to_nas(project_root: Path | None = None) -> dict[str, str | int | bool]:
    """Copy knowledge, RAG, logs, handoff to {nas}/lemdesk/. Returns summary."""
    root = project_root or ROOT
    hub = root / "lemdesk"
    nas = _nas_ai_root()
    if not nas:
        return {"ok": False, "reason": "NAS not mounted"}

    dest = nas / "lemdesk"
    copied = 0
    for sub in ("data", "logs"):
        src = hub / sub
        if not src.is_dir():
            continue
        dst = dest / sub
        dst.mkdir(parents=True, exist_ok=True)
        if subprocess.run(["rsync", "-a", "--delete", f"{src}/", f"{dst}/"], check=False).returncode == 0:
            copied += 1

    # Skills from project → NAS
    skills_src = root / ".cursor" / "skills"
    skills_dst = nas / "skills"
    if skills_src.is_dir():
        skills_dst.mkdir(parents=True, exist_ok=True)
        for skill_dir in skills_src.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                target = skills_dst / skill_dir.name
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(skill_dir / "SKILL.md", target / "SKILL.md")

    return {"ok": True, "dest": str(dest), "mirrored_dirs": copied, "nas": str(nas)}
