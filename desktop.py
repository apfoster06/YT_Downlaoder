#!/usr/bin/env python3
"""
desktop.py — packaged-app entry point.

Starts the Flask app with a production WSGI server (waitress) on a free local
port in a background thread, then shows it in a native desktop window via
pywebview (Edge WebView2 on Windows, WKWebView on macOS). No browser, no console.

Run in dev:   python desktop.py
Frozen:       built by build_exe.py / PyInstaller into a single .exe
"""

from __future__ import annotations

import socket
import threading
import time

import webview
from waitress import serve

from webapp import DOWNLOAD_DIR, app
from runtime_paths import APP_NAME, app_icon


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(port: int) -> None:
    # waitress is a real WSGI server — robust enough to ship, and bundles cleanly.
    serve(app, host="127.0.0.1", port=port, threads=8, _quiet=True)


def _wait_until_up(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    _wait_until_up(port)

    webview.create_window(
        f"{APP_NAME} · fostfam.cloud",
        f"http://127.0.0.1:{port}/",
        width=900,
        height=940,
        min_size=(580, 640),
    )
    # Without this the window borrows whatever icon sys.executable has — the
    # generic Python feather when running from source.
    webview.start(icon=app_icon())


if __name__ == "__main__":
    main()
