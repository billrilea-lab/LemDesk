"""Local status API for LEMdesk Pro dashboard."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

import httpx

STATIC = Path(__file__).parent / "static"
DEFAULT_PORT = 8765


class _Handler(BaseHTTPRequestHandler):
    get_health: Callable[[], dict] = staticmethod(lambda: {"score": 0})
    get_desk_pack: Callable[[], dict | None] = staticmethod(lambda: None)

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/dashboard"):
            self._send_file(STATIC / "dashboard.html", "text/html; charset=utf-8")
            return
        if self.path == "/health":
            self._send_json(self.get_health())
            return
        if self.path == "/desk-pack":
            pack = self.get_desk_pack()
            if pack is None:
                self._send_json({"error": "No desk pack — run lemdesk-smart-handoff"}, 404)
                return
            self._send_json(pack)
            return
        if self.path.startswith("/static/"):
            rel = self.path[len("/static/") :]
            target = STATIC / rel
            if target.is_file():
                ctype = "text/css" if rel.endswith(".css") else "application/octet-stream"
                self._send_file(target, ctype)
                return
        self.send_error(404)


def _port_serves_lemdesk(port: int) -> bool:
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.5)
        if r.status_code != 200:
            return False
        data = r.json()
        return data.get("product") == "LEMdesk Pro"
    except Exception:
        return False


def start_status_server(
    port: int = DEFAULT_PORT,
    get_health: Callable[[], dict] | None = None,
    get_desk_pack: Callable[[], dict | None] | None = None,
) -> ThreadingHTTPServer | None:
    """Start background HTTP server; returns server or None if port already has LEMdesk."""
    from lemdesk_pro.desk_health import run_health_check
    from lemdesk_pro.smart_handoff import DESK_PACK

    def _health() -> dict:
        if get_health:
            return get_health()
        return run_health_check()

    def _pack() -> dict | None:
        if get_desk_pack:
            return get_desk_pack()
        if DESK_PACK.exists():
            return json.loads(DESK_PACK.read_text())
        return None

    _Handler.get_health = staticmethod(_health)
    _Handler.get_desk_pack = staticmethod(_pack)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    except OSError as exc:
        if exc.errno in (48, 98) and _port_serves_lemdesk(port):
            return None
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
