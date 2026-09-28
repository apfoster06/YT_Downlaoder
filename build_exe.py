#!/usr/bin/env python3
"""
build_exe.py — freeze the desktop app into a single executable with PyInstaller.

Bundles: templates/, assets/icon.ico, bin/ffmpeg + ffprobe, yt-dlp (incl.
extractors), the pywebview backend, certifi and brotli. Builds to a local
(non-OneDrive) folder so the large build/dist trees don't get synced.

The icon is generated first if it's missing, so a fresh clone builds in one go.

Usage:   python build_exe.py
Output:  ~/yt_build/dist/YT-Grabber(.exe)

Cross-platform-ready: uses os.pathsep and only adds the Windows webview backend
hidden-imports on Windows, so the same script can build a .app on macOS later.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).parent.resolve()
SEP = os.pathsep  # ';' on Windows, ':' on macOS/Linux
IS_WIN = platform.system() == "Windows"
APP = "YT-Grabber"
BUILD_ROOT = Path.home() / "yt_build"


def main() -> None:
    ffmpeg = "ffmpeg.exe" if IS_WIN else "ffmpeg"
    ffprobe = "ffprobe.exe" if IS_WIN else "ffprobe"

    icon = HERE / "assets" / "icon.ico"
    if not icon.exists():
        print("assets/icon.ico missing — generating it…")
        import make_icon

        make_icon.main()

    args = [
        str(HERE / "desktop.py"),
        "--name", APP,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={icon}",
        f"--add-data={icon}{SEP}assets",
        f"--add-data={HERE / 'templates'}{SEP}templates",
        f"--add-binary={HERE / 'bin' / ffmpeg}{SEP}bin",
        f"--add-binary={HERE / 'bin' / ffprobe}{SEP}bin",
        "--collect-all", "yt_dlp",
        "--collect-all", "webview",
        "--collect-all", "certifi",
        "--collect-submodules", "waitress",
        "--hidden-import", "brotli",
        "--distpath", str(BUILD_ROOT / "dist"),
        "--workpath", str(BUILD_ROOT / "build"),
        "--specpath", str(BUILD_ROOT),
    ]
    if IS_WIN:
        args += [
            "--hidden-import", "clr",
            "--hidden-import", "webview.platforms.winforms",
            "--hidden-import", "webview.platforms.edgechromium",
        ]

    PyInstaller.__main__.run(args)

    exe = BUILD_ROOT / "dist" / (APP + (".exe" if IS_WIN else ""))
    print("\n" + "=" * 60)
    print("BUILT:" if exe.exists() else "NOT FOUND (check log above):", exe)
    print("=" * 60)


if __name__ == "__main__":
    main()
