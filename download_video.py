#!/usr/bin/env python3
"""
download_video.py — fetch a video from YouTube (or any yt-dlp-supported site).

Two modes:
  1. Inspect  — print metadata (title, uploader, duration, license) WITHOUT
                downloading, so you can verify you have the rights to the content.
  2. Download — pull the actual media once you've confirmed rights.

You are responsible for confirming you have the right to download any given URL
(your own uploads, Creative Commons / public-domain material, or content you're
otherwise licensed to use).

Requires:
  pip install -U yt-dlp
  ffmpeg on PATH (needed to merge separate video+audio streams)

Examples:
  # 1) Inspect first — no download, just metadata
  python download_video.py --inspect "https://youtu.be/XXXXXXXXXXX"

  # 2) Download best quality into ./downloads
  python download_video.py "https://youtu.be/XXXXXXXXXXX"

  # 3) Cap resolution and pick an output folder
  python download_video.py --max-height 720 -o "D:/clips" "https://..."

  # 4) Audio only (extracted to mp3)
  python download_video.py --audio "https://..."
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp is not installed. Run:  pip install -U yt-dlp")


def _check_ffmpeg() -> str | None:
    """Return the path to ffmpeg, or None if it isn't on PATH."""
    return shutil.which("ffmpeg")


def inspect(url: str) -> dict:
    """Fetch and print metadata for a URL without downloading anything."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    fields = [
        ("Title", info.get("title")),
        ("Uploader", info.get("uploader")),
        ("Channel", info.get("channel")),
        ("Duration", info.get("duration_string")),
        ("Resolution", info.get("resolution")),
        ("License", info.get("license") or "NA"),
        ("Upload date", info.get("upload_date")),
        ("View count", info.get("view_count")),
        ("Webpage", info.get("webpage_url")),
    ]
    print("\n--- Video metadata (verify rights before downloading) ---")
    for label, value in fields:
        if value is not None:
            print(f"  {label:12}: {value}")
    print("---------------------------------------------------------\n")
    return info


def build_options(
    output_dir: Path,
    max_height: int | None,
    audio_only: bool,
) -> dict:
    """Assemble the yt-dlp options dict for a download."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(title)s [%(id)s].%(ext)s")

    opts: dict = {
        "outtmpl": outtmpl,
        "noplaylist": True,          # a single URL = a single video
        "restrictfilenames": True,   # filesystem-safe names (good on Windows)
        "ignoreerrors": False,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
    }

    # Prefer a ffmpeg bundled alongside a frozen (PyInstaller) build; otherwise
    # fall back to whatever is on PATH.
    bundled = None
    try:
        from runtime_paths import bundled_ffmpeg_dir

        bundled = bundled_ffmpeg_dir()
    except Exception:
        bundled = None
    if bundled:
        opts["ffmpeg_location"] = bundled
    else:
        ffmpeg = _check_ffmpeg()
        if ffmpeg:
            # yt-dlp auto-detects ffmpeg on PATH; set explicitly to be safe.
            opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # Prefer mp4 video + m4a audio so the merged result is a clean .mp4.
        if max_height:
            fmt = (
                f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_height}]+bestaudio/"
                f"best[height<={max_height}]"
            )
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        opts["format"] = fmt
        opts["merge_output_format"] = "mp4"

    return opts


def download(url: str, opts: dict) -> int:
    """Run the actual download. Returns the yt-dlp exit code (0 == success)."""
    if not _check_ffmpeg():
        print(
            "WARNING: ffmpeg not found on PATH. Merging video+audio or "
            "extracting mp3 will fail. Install ffmpeg and retry.\n",
            file=sys.stderr,
        )
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.download([url])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download a video (or audio) from a yt-dlp-supported URL."
    )
    parser.add_argument("url", help="The video URL.")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print metadata only; do NOT download. Use this to verify rights.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("downloads"),
        help="Folder to save into (default: ./downloads).",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=None,
        help="Cap video resolution, e.g. 1080 or 720 (default: best available).",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Download audio only and extract to mp3.",
    )
    args = parser.parse_args(argv)

    # Always show metadata first so you can sanity-check what you're pulling.
    try:
        inspect(args.url)
    except Exception as exc:  # noqa: BLE001 - surface any extractor error plainly
        print(f"Could not fetch metadata: {exc}", file=sys.stderr)
        return 1

    if args.inspect:
        print("Inspect mode: nothing downloaded.")
        return 0

    opts = build_options(args.output_dir, args.max_height, args.audio)
    code = download(args.url, opts)
    if code == 0:
        print(f"\nDone. Saved into: {args.output_dir.resolve()}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
