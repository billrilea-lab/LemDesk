"""LEMdesk Pro license check — founding member keys + Stripe paste flow."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

LICENSE_DIR = Path.home() / ".config" / "lemdesk"
LICENSE_FILE = LICENSE_DIR / "license.key"
PREFIX = "LEMP-"

# Founding keys (demo — replace with Stripe webhook / license server at scale)
_BUILTIN_KEYS = frozenset(
    {
        "LEMP-FOUNDING-MACMINI2-2026",
        "LEMP-FOUNDING-DEMO-2026",
    }
)


def _normalize(key: str) -> str:
    return key.strip().upper().replace(" ", "")


def _key_valid(key: str) -> bool:
    k = _normalize(key)
    if not k.startswith(PREFIX) or len(k) < 16:
        return False
    if k in _BUILTIN_KEYS:
        return True
    # Stripe-style: LEMP- + 32 hex from checkout metadata
    suffix = k[len(PREFIX) :]
    if len(suffix) >= 24 and all(c in "0123456789ABCDEF-" for c in suffix):
        return True
    return False


def read_license_key() -> str | None:
    env = os.environ.get("LEMDESK_PRO_LICENSE", "").strip()
    if env and _key_valid(env):
        return _normalize(env)
    if LICENSE_FILE.exists():
        key = LICENSE_FILE.read_text().strip()
        if _key_valid(key):
            return _normalize(key)
    return None


def is_pro_licensed(*, dev_mode: bool = False) -> bool:
    if dev_mode or os.environ.get("LEMDESK_PRO_DEV") == "1":
        return True
    if os.environ.get("LEMDESK_PRO_SKIP_LICENSE") == "1":
        return True
    return read_license_key() is not None


def save_license_key(key: str) -> Path:
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    k = _normalize(key)
    if not _key_valid(k):
        raise ValueError(f"Invalid license format — expected {PREFIX}…")
    LICENSE_FILE.write_text(k + "\n")
    LICENSE_FILE.chmod(0o600)
    return LICENSE_FILE


def generate_machine_key(hostname: str | None = None) -> str:
    """Deterministic founding key from hostname (installer use)."""
    host = (hostname or platform.node().split(".")[0]).upper().replace(" ", "-")[:24]
    digest = hashlib.sha256(host.encode()).hexdigest()[:12].upper()
    return f"{PREFIX}{host}-{digest}"


def license_status() -> dict[str, object]:
    key = read_license_key()
    return {
        "licensed": key is not None,
        "key_preview": f"{key[:12]}…" if key and len(key) > 12 else key,
        "path": str(LICENSE_FILE),
        "dev_mode": os.environ.get("LEMDESK_PRO_DEV") == "1",
    }


def require_pro_license(*, dev_mode: bool = False) -> None:
    if is_pro_licensed(dev_mode=dev_mode):
        return
    msg = (
        "LEMdesk Pro requires a license.\n\n"
        f"Paste your key into:\n  {LICENSE_FILE}\n\n"
        "Or run:\n  python3 bot.py lemdesk-license --set LEMP-…\n\n"
        "Founding members: https://lemdev.com/pricing.html\n"
        "Dev bypass: python3 bot.py lemdesk-pro --dev"
    )
    if platform.system() == "Darwin":
        try:
            import rumps

            rumps.alert("LEMdesk Pro — license required", msg, ok="OK")
        except ImportError:
            print(msg, file=__import__("sys").stderr)
    else:
        print(msg, file=__import__("sys").stderr)
    raise SystemExit(2)
