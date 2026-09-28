#!/usr/bin/env python3
"""
gui.py — a small CustomTkinter front-end for download_video.py.

Paste a URL, optionally tweak the options, and hit "Download Video".
A progress bar + status line show download progress, speed and ETA.
"Inspect" fetches metadata only (no download) so you can verify rights first.

The actual download runs on a background thread so the window never freezes;
progress updates are marshalled back to the UI thread through a queue.

Run:
  python gui.py
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

try:
    import yt_dlp
except ImportError:
    raise SystemExit("yt-dlp is not installed. Run:  pip install -U yt-dlp")

# Reuse the format-selection logic from the CLI tool.
from download_video import build_options

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

QUALITY_CHOICES = {
    "Best available": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
}


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YT Downloader")
        self.geometry("640x520")
        self.minsize(560, 480)

        # Thread -> UI message channel.
        self._q: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None

        self.grid_columnconfigure(0, weight=1)

        # --- URL row -------------------------------------------------------
        ctk.CTkLabel(self, text="Video URL", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(16, 0)
        )
        self.url_entry = ctk.CTkEntry(self, placeholder_text="https://youtu.be/…")
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 8))

        # --- Output folder row --------------------------------------------
        out_frame = ctk.CTkFrame(self, fg_color="transparent")
        out_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        out_frame.grid_columnconfigure(0, weight=1)

        self.out_entry = ctk.CTkEntry(out_frame)
        self.out_entry.insert(0, str((Path(__file__).parent / "downloads").resolve()))
        self.out_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(out_frame, text="Browse…", width=90, command=self._browse).grid(
            row=0, column=1
        )

        # --- Options row ---------------------------------------------------
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=4)

        ctk.CTkLabel(opt_frame, text="Quality:").grid(row=0, column=0, padx=(0, 8))
        self.quality_menu = ctk.CTkOptionMenu(
            opt_frame, values=list(QUALITY_CHOICES.keys()), width=160
        )
        self.quality_menu.set("Best available")
        self.quality_menu.grid(row=0, column=1, padx=(0, 16))

        self.audio_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opt_frame, text="Audio only (mp3)", variable=self.audio_var
        ).grid(row=0, column=2)

        # --- Action buttons ------------------------------------------------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(8, 4))
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.inspect_btn = ctk.CTkButton(
            btn_frame, text="Inspect (verify rights)", command=self._on_inspect
        )
        self.inspect_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.download_btn = ctk.CTkButton(
            btn_frame, text="Download Video", command=self._on_download
        )
        self.download_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # --- Progress + status --------------------------------------------
        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=5, column=0, sticky="ew", padx=16, pady=(12, 2))

        self.status = ctk.CTkLabel(self, text="Idle.", anchor="w")
        self.status.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 4))

        # --- Log box -------------------------------------------------------
        self.grid_rowconfigure(7, weight=1)
        self.log = ctk.CTkTextbox(self, activate_scrollbars=True)
        self.log.grid(row=7, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self.log.configure(state="disabled")

        # Begin polling the worker->UI queue.
        self.after(100, self._poll_queue)

    # ----------------------------------------------------------------- utils
    def _browse(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.out_entry.get() or ".")
        if folder:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, folder)

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.inspect_btn.configure(state=state)
        self.download_btn.configure(state=state)

    # -------------------------------------------------------------- actions
    def _on_inspect(self) -> None:
        self._start(self._run_inspect)

    def _on_download(self) -> None:
        self._start(self._run_download)

    def _start(self, target) -> None:
        url = self.url_entry.get().strip()
        if not url:
            self._log("Please paste a URL first.")
            return
        if self._worker and self._worker.is_alive():
            self._log("A job is already running — please wait.")
            return
        self._set_busy(True)
        self.progress.set(0)
        self.status.configure(text="Working…")
        self._worker = threading.Thread(target=target, args=(url,), daemon=True)
        self._worker.start()

    # ---------------------------------------------------- worker-thread jobs
    def _run_inspect(self, url: str) -> None:
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            lines = [
                "--- Metadata (verify rights before downloading) ---",
                f"  Title    : {info.get('title')}",
                f"  Uploader : {info.get('uploader')}",
                f"  Duration : {info.get('duration_string')}",
                f"  Quality  : {info.get('resolution')}",
                f"  License  : {info.get('license') or 'NA'}",
                f"  Uploaded : {info.get('upload_date')}",
                "---------------------------------------------------",
            ]
            self._q.put(("log", "\n".join(lines)))
            self._q.put(("status", "Inspect complete — nothing downloaded."))
            self._q.put(("done", None))
        except Exception as exc:  # noqa: BLE001
            self._q.put(("error", f"Inspect failed: {exc}"))

    def _run_download(self, url: str) -> None:
        try:
            out_dir = Path(self.out_entry.get().strip() or "downloads")
            max_height = QUALITY_CHOICES[self.quality_menu.get()]
            audio_only = self.audio_var.get()

            opts = build_options(out_dir, max_height, audio_only)
            opts.update(
                {
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [self._progress_hook],
                    "logger": _QueueLogger(self._q),
                }
            )
            self._q.put(("log", f"Starting download → {out_dir}"))
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self._q.put(("status", f"Done. Saved into: {out_dir}"))
            self._q.put(("progress", 1.0))
            self._q.put(("log", "Download complete."))
            self._q.put(("done", None))
        except Exception as exc:  # noqa: BLE001
            self._q.put(("error", f"Download failed: {exc}"))

    def _progress_hook(self, d: dict) -> None:
        """Runs on the worker thread — only push messages, never touch widgets."""
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes", 0)
            if total:
                self._q.put(("progress", done / total))
            speed = d.get("speed")
            eta = d.get("eta")
            speed_txt = f"{speed / 1_048_576:.1f} MB/s" if speed else "—"
            pct = f"{done / total * 100:.0f}%" if total else "…"
            self._q.put(("status", f"Downloading {pct}  ·  {speed_txt}  ·  ETA {eta or '—'}s"))
        elif status == "finished":
            self._q.put(("status", "Merging / post-processing…"))
            self._q.put(("progress", 1.0))

    # ----------------------------------------------------- UI-thread polling
    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "status":
                    self.status.configure(text=payload)
                elif kind == "progress":
                    self.progress.set(payload)
                elif kind == "error":
                    self._log(payload)
                    self.status.configure(text="Error — see log.")
                    self._set_busy(False)
                elif kind == "done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


class _QueueLogger:
    """yt-dlp logger that forwards messages to the UI queue."""

    def __init__(self, q: queue.Queue) -> None:
        self._q = q

    def debug(self, msg: str) -> None:
        # yt-dlp routes normal output through debug(); keep only real lines.
        if msg and not msg.startswith("[debug]"):
            self._q.put(("log", msg))

    def info(self, msg: str) -> None:
        self._q.put(("log", msg))

    def warning(self, msg: str) -> None:
        self._q.put(("log", f"WARNING: {msg}"))

    def error(self, msg: str) -> None:
        self._q.put(("log", f"ERROR: {msg}"))


if __name__ == "__main__":
    App().mainloop()
