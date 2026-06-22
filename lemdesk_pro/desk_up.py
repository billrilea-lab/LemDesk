"""Desk Up — one-shot morning startup for LEMdesk Pro (Docker, DMR, mounts, health)."""

from __future__ import annotations

import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
DMR_PORT = 12434
GC_MM2 = Path("/Volumes/GC-MM2")
NAS_AI = Path("/Volumes/docker/AI")
MODELS_LINK = Path.home() / ".docker" / "models"


def _say(msg: str) -> None:
    print(msg)


def _mount_ok(path: Path, label: str) -> dict[str, Any]:
    if path.is_dir():
        return {"id": label, "status": "ok", "detail": str(path)}
    return {"id": label, "status": "fail", "detail": f"Not mounted: {path}"}


def check_storage() -> list[dict[str, Any]]:
    """Volumes and model symlink (Mac Mini small SSD layout)."""
    out = [
        _mount_ok(GC_MM2, "gc_mm2"),
        _mount_ok(NAS_AI, "nas_ai"),
    ]
    if MODELS_LINK.is_symlink():
        target = MODELS_LINK.resolve()
        on_external = str(target).startswith("/Volumes/")
        out.append(
            {
                "id": "dmr_models",
                "status": "ok" if on_external else "warn",
                "detail": f"~/.docker/models → {MODELS_LINK.readlink()}",
            }
        )
    elif MODELS_LINK.is_dir():
        out.append(
            {
                "id": "dmr_models",
                "status": "warn",
                "detail": "Models on internal SSD — run relocate_storage.sh --apply",
            }
        )
    else:
        out.append({"id": "dmr_models", "status": "ok", "detail": "No local models yet"})
    return out


def ensure_docker(wait_sec: int = 90) -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if platform.system() != "Darwin":
        return False

    _say("Starting Docker Desktop…")
    subprocess.run(["open", "-a", "Docker"], check=False)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            time.sleep(2)
    return False


def ensure_dmr() -> dict[str, Any]:
    subprocess.run(
        ["docker", "desktop", "enable", "model-runner"],
        capture_output=True,
        text=True,
    )
    url = f"http://127.0.0.1:{DMR_PORT}/engines/v1/models"
    try:
        r = httpx.get(url, timeout=8.0)
        if r.status_code == 200:
            data = r.json()
            models = data.get("data") or []
            return {
                "status": "ok",
                "detail": f"{len(models)} model(s) on :{DMR_PORT}",
                "models": len(models),
            }
        return {"status": "warn", "detail": f"DMR HTTP {r.status_code}"}
    except Exception as exc:
        return {"status": "fail", "detail": f"DMR unreachable — {exc.__class__.__name__}"}


def run_desk_up(*, sync: bool = False, open_nas: bool = False) -> dict[str, Any]:
    """Bring the desk online; return summary dict."""
    from lemdesk_pro.desk_health import run_health_check

    report: dict[str, Any] = {"steps": [], "storage": check_storage()}

    for s in report["storage"]:
        icon = "✓" if s["status"] == "ok" else "!"
        _say(f"  [{icon}] {s['id']}: {s['detail']}")
        if s["status"] == "fail" and s["id"] == "nas_ai" and open_nas and platform.system() == "Darwin":
            subprocess.run(
                ["open", "smb://DiskRack1SDR._smb._tcp.local/docker"],
                check=False,
            )
            _say("  → Opening NAS mount dialog…")

    if not ensure_docker():
        report["steps"].append({"step": "docker", "status": "fail"})
        _say("  [✗] Docker did not start — open Docker Desktop manually")
    else:
        report["steps"].append({"step": "docker", "status": "ok"})
        _say("  [✓] Docker engine")

        dmr = ensure_dmr()
        report["dmr"] = dmr
        icon = "✓" if dmr["status"] == "ok" else "✗" if dmr["status"] == "fail" else "!"
        _say(f"  [{icon}] Model Runner: {dmr['detail']}")

    if sync:
        _say("  […] lemdesk-sync --fast")
        subprocess.run(
            ["python3", str(ROOT / "bot.py"), "lemdesk-sync", "--fast", "--skip-dmr-check"],
            cwd=ROOT,
            check=False,
        )
        report["steps"].append({"step": "sync", "status": "ok"})

    health = run_health_check()
    report["health"] = health
    _say("")
    _say(f"Desk Health: {health['score']}/100 ({health['grade']})")
    _say(health["summary"])
    return report
