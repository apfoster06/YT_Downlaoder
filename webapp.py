#!/usr/bin/env python3
"""
webapp.py — a local Flask website for the YT Downloader, styled like fostfam.cloud.

Features:
  - Paste a URL, inspect metadata (verify rights), then download.
  - Quality selection + audio-only (mp3).
  - Optional "Trim video": give start/end timecodes (e.g. :07 - 12:33) and only
    that section is fetched (via yt-dlp download sections + ffmpeg keyframe cuts).
  - Live progress (percent / speed / ETA) via a background job + polling API.

Local only — binds to 127.0.0.1. You are responsible for confirming you have the
right to download any given URL.

Run:
  python webapp.py
  then open http://127.0.0.1:8093
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

try:
    import yt_dlp
except ImportError:
    raise SystemExit("yt-dlp is not installed. Run:  pip install -U yt-dlp")

# Reuse the format-selection logic from the CLI tool.
from download_video import build_options
from runtime_paths import app_icon, downloads_dir, ffmpeg_exe, resource_path

APP_DIR = Path(__file__).parent
DOWNLOAD_DIR = downloads_dir()  # <user Downloads>/YT Grabber
PORT = 8093

app = Flask(__name__, template_folder=resource_path("templates"))

# ----------------------------------------------------------------- job store
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

QUALITY = {"best": None, "1080": 1080, "720": 720, "480": 480}


def parse_timecode(value: str | None) -> int | None:
    """Parse ':07', '12:33', '1:02:33' → seconds. Empty → None. Raises on junk."""
    s = (value or "").strip()
    if not s:
        return None
    if not re.fullmatch(r"[0-9:]+", s):
        raise ValueError(f"'{value}' is not a valid timecode")
    total = 0
    for part in s.split(":"):
        total = total * 60 + (int(part) if part else 0)
    return total


def _new_job() -> str:
    jid = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[jid] = {
            "status": "starting",
            "percent": 0.0,
            "speed": None,
            "eta": None,
            "log": [],
            "filename": None,
            "filepath": None,
            "error": None,
        }
    return jid


def _update(jid: str, **kw) -> None:
    with _lock:
        if jid in _jobs:
            _jobs[jid].update(kw)


def _log(jid: str, msg: str) -> None:
    if not msg:
        return
    with _lock:
        if jid in _jobs:
            _jobs[jid]["log"].append(msg.rstrip())
            _jobs[jid]["log"] = _jobs[jid]["log"][-200:]


class _JobLogger:
    """yt-dlp logger that records messages onto the job."""

    def __init__(self, jid: str) -> None:
        self.jid = jid

    def debug(self, msg: str) -> None:
        if msg and not msg.startswith("[debug]"):
            _log(self.jid, msg)

    def info(self, msg: str) -> None:
        _log(self.jid, msg)

    def warning(self, msg: str) -> None:
        _log(self.jid, f"WARNING: {msg}")

    def error(self, msg: str) -> None:
        _log(self.jid, f"ERROR: {msg}")


def _hook(jid: str, d: dict) -> None:
    status = d.get("status")
    if status == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        done = d.get("downloaded_bytes", 0)
        _update(
            jid,
            status="downloading",
            percent=(done / total) if total else 0.0,
            speed=d.get("speed"),
            eta=d.get("eta"),
        )
    elif status == "finished":
        _update(jid, status="processing", percent=1.0)


def _ffmpeg_trim(src_path: str, start, end, jid: str) -> str | None:
    """Cut [start, end] out of an already-downloaded file with ffmpeg.

    Tries a fast lossless stream-copy first (keyframe-accurate start); falls
    back to re-encoding the segment if the container/codec won't copy cleanly.
    Returns the new file path, or None on failure.
    """
    src = Path(src_path)
    lo = start or 0
    out = src.with_name(f"{src.stem}_clip{src.suffix}")
    ffmpeg = ffmpeg_exe()

    base = [ffmpeg, "-y", "-ss", str(lo), "-i", str(src)]
    if end is not None:
        base += ["-t", str(max(0.0, end - lo))]

    span = f"{lo}s–{end if end is not None else 'end'}"
    _log(jid, f"Trimming to {span} (fast lossless copy)…")
    copy_cmd = base + ["-c", "copy", str(out)]
    proc = subprocess.run(copy_cmd, capture_output=True, text=True)
    if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
        return str(out)

    # Fallback: re-encode the segment.
    _log(jid, "Lossless copy didn't take — re-encoding the segment…")
    out.unlink(missing_ok=True)
    is_audio = src.suffix.lower() in {".mp3", ".m4a", ".aac", ".opus", ".wav", ".flac"}
    if is_audio:
        enc = ["-c:a", "libmp3lame" if src.suffix.lower() == ".mp3" else "aac"]
    else:
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac"]
    proc = subprocess.run(base + enc + [str(out)], capture_output=True, text=True)
    if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
        return str(out)

    _log(jid, f"ffmpeg trim failed: {(proc.stderr or '')[-300:]}")
    return None


def _worker(jid, url, quality, audio, start, end) -> None:
    try:
        opts = build_options(DOWNLOAD_DIR, QUALITY.get(quality), audio)
        opts.update(
            {
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [lambda d: _hook(jid, d)],
                "logger": _JobLogger(jid),
            }
        )
        _update(jid, status="downloading")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Resolve the final file path.
        filepath = None
        reqs = info.get("requested_downloads") or []
        if reqs:
            filepath = reqs[0].get("filepath")
        filepath = filepath or info.get("filepath")
        if not filepath or not Path(filepath).exists():
            files = sorted(
                DOWNLOAD_DIR.glob("*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            filepath = str(files[0]) if files else None

        # Trim locally with ffmpeg if a section was requested. (yt-dlp's own
        # section download is unreliably slow for these formats, so we fetch
        # the whole file and cut it here instead.)
        if filepath and (start is not None or end is not None):
            _update(jid, status="processing")
            trimmed = _ffmpeg_trim(filepath, start, end, jid)
            if trimmed:
                if Path(trimmed) != Path(filepath):
                    Path(filepath).unlink(missing_ok=True)  # drop the full file
                filepath = trimmed

        if filepath:
            _update(
                jid,
                status="done",
                percent=1.0,
                filename=Path(filepath).name,
                filepath=filepath,
            )
            _log(jid, f"Saved: {Path(filepath).name}")
        else:
            _update(jid, status="done", percent=1.0)
            _log(jid, "Finished, but could not locate the output file.")
    except Exception as exc:  # noqa: BLE001
        _update(jid, status="error", error=str(exc))
        _log(jid, f"ERROR: {exc}")


# --------------------------------------------------------------------- routes
@app.route("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    icon = app_icon()
    if not icon:
        abort(404)
    return send_file(icon, mimetype="image/x-icon")


@app.post("/api/inspect")
def api_inspect():
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not url:
        return jsonify(error="Please paste a URL."), 400
    try:
        with yt_dlp.YoutubeDL(
            {"quiet": True, "no_warnings": True, "skip_download": True}
        ) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=str(exc)), 400
    return jsonify(
        title=info.get("title"),
        uploader=info.get("uploader"),
        duration=info.get("duration_string"),
        resolution=info.get("resolution"),
        license=info.get("license") or "NA",
        upload_date=info.get("upload_date"),
        thumbnail=info.get("thumbnail"),
    )


@app.post("/api/download")
def api_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify(error="Please paste a URL."), 400

    start = end = None
    if data.get("trim"):
        try:
            start = parse_timecode(data.get("start"))
            end = parse_timecode(data.get("end"))
        except ValueError as exc:
            return jsonify(error=f"Invalid trim time: {exc}"), 400
        if start is not None and end is not None and end <= start:
            return jsonify(error="Trim end must be after the start time."), 400

    jid = _new_job()
    threading.Thread(
        target=_worker,
        args=(jid, url, data.get("quality", "best"), bool(data.get("audio")), start, end),
        daemon=True,
    ).start()
    return jsonify(job_id=jid)


@app.get("/api/progress/<jid>")
def api_progress(jid):
    with _lock:
        job = _jobs.get(jid)
        if not job:
            return jsonify(error="unknown job"), 404
        out = {k: job[k] for k in ("status", "percent", "speed", "eta", "filename", "error")}
        out["log"] = job["log"][-12:]
    return jsonify(out)


@app.get("/api/file/<jid>")
def api_file(jid):
    with _lock:
        job = _jobs.get(jid)
    if not job or not job.get("filepath") or not Path(job["filepath"]).exists():
        abort(404)
    return send_file(job["filepath"], as_attachment=True, download_name=job["filename"])


if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"YT Downloader running at http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
