"""
runtime_paths.py — path helpers that work both in dev and inside a frozen
PyInstaller bundle.

When PyInstaller freezes the app, bundled data (templates, ffmpeg) is unpacked
to a temp dir exposed as ``sys._MEIPASS``. In dev it's just this file's folder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "YT Grabber"


def resource_path(relative: str) -> str:
    """Absolute path to a bundled resource (works frozen or in dev)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundled_ffmpeg_dir() -> str | None:
    """Directory holding bundled ffmpeg/ffprobe when frozen, else None (use PATH)."""
    if is_frozen():
        d = resource_path("bin")
        if os.path.isdir(d):
            return d
    return None


def ffmpeg_exe() -> str:
    """Path to the ffmpeg executable to use (bundled if frozen, else PATH)."""
    d = bundled_ffmpeg_dir()
    if d:
        return os.path.join(d, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    import shutil

    return shutil.which("ffmpeg") or "ffmpeg"


def app_icon() -> str | None:
    """Path to the app icon (.ico), or None if it hasn't been generated yet.

    Frozen builds get it from the bundle; in dev it comes from ./assets, which
    only exists once ``python make_icon.py`` has been run.
    """
    p = resource_path(os.path.join("assets", "icon.ico"))
    return p if os.path.isfile(p) else None


def downloads_dir() -> Path:
    """Where finished videos go: <user Downloads>/YT Grabber (created on demand)."""
    base = Path.home() / "Downloads"
    if not base.exists():
        base = Path.home()
    target = base / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target
