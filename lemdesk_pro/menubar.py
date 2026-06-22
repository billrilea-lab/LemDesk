"""LEMdesk Pro menu bar app (macOS) with CLI fallback."""

from __future__ import annotations

import platform
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8765


def _run_sync() -> None:
    bot = ROOT / "bot.py"
    auto = ROOT / "lemdesk_auto.py"
    if bot.exists():
        subprocess.Popen(
            [sys.executable, str(bot), "lemdesk-sync", "--fast", "--skip-dmr-check"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif auto.exists():
        subprocess.Popen(
            [sys.executable, str(auto), "--fast", "--skip-dmr-check"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def run_cli_fallback(port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    """Headless mode when rumps is unavailable (Linux/SSH)."""
    from lemdesk_pro.desk_health import run_health_check
    from lemdesk_pro.status_server import start_status_server

    health = run_health_check()
    print(f"LEMdesk Pro (CLI) — health {health['score']}/100 ({health['grade']})")
    print(f"Dashboard: http://127.0.0.1:{port}/")
    print("Ctrl+C to stop")
    start_status_server(port=port)
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopped.")


def run_menubar(port: int = DEFAULT_PORT, open_dashboard: bool = True) -> None:
    if platform.system() != "Darwin":
        print("Menu bar is macOS-only — starting CLI dashboard instead.")
        run_cli_fallback(port, open_browser=open_dashboard)
        return

    try:
        import rumps
    except ImportError:
        print("Install menu bar deps: pip install rumps")
        print("Starting CLI dashboard instead.")
        run_cli_fallback(port, open_browser=open_dashboard)
        return

    from lemdesk_pro.desk_health import run_health_check
    from lemdesk_pro.smart_handoff import write_smart_handoff
    from lemdesk_pro.status_server import start_status_server

    start_status_server(port=port)

    class LemdeskProApp(rumps.App):
        def __init__(self) -> None:
            super().__init__("LEMdesk", quit_button=None)
            self.port = port
            self.menu = [
                rumps.MenuItem("Desk Up", callback=self.desk_up),
                rumps.MenuItem("Open Dashboard", callback=self.open_dashboard),
                rumps.MenuItem("Desk Health", callback=self.show_health),
                None,
                rumps.MenuItem("Sync Now", callback=self.sync_now),
                rumps.MenuItem("Smart Handoff", callback=self.smart_handoff),
                None,
                rumps.MenuItem("Quit", callback=self.quit_app),
            ]
            self._refresh_title()

        def _refresh_title(self) -> None:
            h = run_health_check()
            self.title = f" {h['score']}{h['grade']}"

        @rumps.timer(3)
        def boot_dashboard(self, sender: object) -> None:
            if open_dashboard:
                webbrowser.open(f"http://127.0.0.1:{self.port}/")
            sender.stop()

        @rumps.timer(30)
        def poll_health(self, _: object) -> None:
            self._refresh_title()

        def open_dashboard(self, _: object) -> None:
            webbrowser.open(f"http://127.0.0.1:{self.port}/")

        def desk_up(self, _: object) -> None:
            from lemdesk_pro.desk_up import run_desk_up

            rumps.notification("LEMdesk Pro", "Desk Up", "Checking Docker, DMR, and mounts…")
            run_desk_up(open_nas=True)
            self._refresh_title()
            h = run_health_check()
            rumps.notification(
                "LEMdesk Pro",
                f"Desk {h['score']}/100 ({h['grade']})",
                h["summary"][:120],
            )

        def show_health(self, _: object) -> None:
            h = run_health_check()
            rumps.alert(
                title=f"Desk Health — {h['score']}/100 ({h['grade']})",
                message=h["summary"],
                ok="OK",
            )

        def sync_now(self, _: object) -> None:
            rumps.notification("LEMdesk Pro", "Sync started", "lemdesk-sync --fast")
            _run_sync()
            rumps.Timer(self._sync_done, 8).start()

        def _sync_done(self, _: object) -> None:
            self._refresh_title()
            rumps.notification("LEMdesk Pro", "Sync complete", "Corpus + handoff updated")

        def smart_handoff(self, _: object) -> None:
            paths = write_smart_handoff()
            self._refresh_title()
            _copy_prompt_to_clipboard(paths["desk_prompt"])
            rumps.notification(
                "LEMdesk Pro",
                "Smart Handoff ready",
                "Prompt copied — paste in your next Cursor room",
            )

        def quit_app(self, _: object) -> None:
            rumps.quit_application()

    LemdeskProApp().run()


def _copy_prompt_to_clipboard(prompt_path: Path) -> None:
    if not prompt_path.exists():
        return
    text = prompt_path.read_text()
    if platform.system() == "Darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
    elif platform.system() == "Linux":
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=False)
