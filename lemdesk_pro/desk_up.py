"""Desk Up — morning startup + self-healing for LEMdesk Pro."""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
DMR_PORT = 12434
GC_MM2 = Path("/Volumes/GC-MM2")
MODELS_LINK = Path.home() / ".docker" / "models"
NAS_SMB = "smb://DiskRack1SDR._smb._tcp.local/docker"


def _nas_ai() -> Path:
    try:
        from lemdesk.path_registry import discover_nas_ai, patch_machine_nas_path

        patch_machine_nas_path()
        p = discover_nas_ai()
        return p if p else Path("/Volumes/docker/AI")
    except Exception:
        return Path("/Volumes/docker/AI")


def _say(msg: str) -> None:
    print(msg, flush=True)


def _mount_ok(path: Path, label: str) -> dict[str, Any]:
    if path.is_dir():
        return {"id": label, "status": "ok", "detail": str(path)}
    return {"id": label, "status": "fail", "detail": f"Not mounted: {path}"}


def check_storage() -> list[dict[str, Any]]:
    nas = _nas_ai()
    out = [_mount_ok(GC_MM2, "gc_mm2"), _mount_ok(nas, "nas_ai")]
    if MODELS_LINK.is_symlink():
        on_external = str(MODELS_LINK.resolve()).startswith("/Volumes/")
        out.append(
            {
                "id": "dmr_models",
                "status": "ok" if on_external else "warn",
                "detail": f"~/.docker/models → {MODELS_LINK.readlink()}",
            }
        )
    elif MODELS_LINK.is_dir() and any(MODELS_LINK.iterdir()):
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


def _heal_storage() -> list[str]:
    """Auto-fix storage issues where safe."""
    actions: list[str] = []
    script = ROOT / "lemdesk" / "scripts" / "relocate_storage.sh"
    if (
        MODELS_LINK.is_dir()
        and not MODELS_LINK.is_symlink()
        and GC_MM2.is_dir()
        and script.exists()
    ):
        _say("  [heal] Relocating DMR models to GC-MM2…")
        subprocess.run(["bash", str(script), "--apply"], cwd=ROOT, check=False)
        actions.append("relocate_models")
    return actions


def ensure_docker(wait_sec: int = 90) -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if platform.system() != "Darwin":
        return False
    _say("  [heal] Starting Docker Desktop…")
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
            models = r.json().get("data") or []
            return {
                "status": "ok",
                "detail": f"{len(models)} model(s) on :{DMR_PORT}",
                "models": len(models),
            }
        return {"status": "warn", "detail": f"DMR HTTP {r.status_code}"}
    except Exception as exc:
        return {"status": "fail", "detail": f"DMR unreachable — {exc.__class__.__name__}"}


def _wait_nas(seconds: int = 12) -> bool:
    nas = _nas_ai()
    for _ in range(seconds):
        if nas.is_dir():
            return True
        time.sleep(1)
    return _nas_ai().is_dir()


def run_desk_up(
    *,
    sync: bool = False,
    open_nas: bool = False,
    heal: bool = False,
    mirror_nas: bool = False,
) -> dict[str, Any]:
    from lemdesk_pro.desk_health import run_health_check

    report: dict[str, Any] = {"steps": [], "storage": check_storage(), "heal_actions": []}

    if heal:
        report["heal_actions"] = _heal_storage()
        report["storage"] = check_storage()

    for s in report["storage"]:
        icon = "✓" if s["status"] == "ok" else "!"
        _say(f"  [{icon}] {s['id']}: {s['detail']}")
        if s["status"] == "fail" and s["id"] == "nas_ai" and open_nas and platform.system() == "Darwin":
            subprocess.run(["open", NAS_SMB], check=False)
            _say("  → NAS mount dialog opened — waiting…")
            if _wait_nas(15):
                from lemdesk.path_registry import patch_machine_nas_path

                patch_machine_nas_path()
                report["storage"] = check_storage()

    if not ensure_docker():
        report["steps"].append({"step": "docker", "status": "fail"})
        _say("  [✗] Docker did not start")
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
            [sys.executable, str(ROOT / "bot.py"), "lemdesk-sync", "--fast", "--skip-dmr-check"],
            cwd=ROOT,
            check=False,
        )
        report["steps"].append({"step": "sync", "status": "ok"})

    if mirror_nas:
        from lemdesk.nas_mirror import mirror_to_nas

        m = mirror_to_nas(ROOT)
        report["nas_mirror"] = m
        if m.get("ok"):
            _say(f"  [✓] NAS mirror → {m.get('dest')}")

    health = run_health_check()
    report["health"] = health

    if heal and health["score"] < 85 and not sync:
        age = next((c for c in health["checks"] if c["id"] == "knowledge"), {})
        if age.get("status") != "ok":
            _say("  [heal] Corpus stale — running sync…")
            subprocess.run(
                [sys.executable, str(ROOT / "bot.py"), "lemdesk-sync", "--fast", "--skip-dmr-check"],
                cwd=ROOT,
                check=False,
            )
            health = run_health_check()
            report["health"] = health

    _say("")
    _say(f"Desk Health: {health['score']}/100 ({health['grade']})")
    _say(health["summary"])
    return report
