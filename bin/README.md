# bin/

Holds the `ffmpeg` and `ffprobe` executables that `build_exe.py` bundles into
the frozen app.

**They are not in git.** The Windows builds used here are ~227 MB each, and
GitHub rejects any single file over 100 MB. After cloning, this folder will be
empty and you need to put them back yourself.

## Do I need them?

| How you run it                        | Needs `bin/`? |
|---------------------------------------|---------------|
| `python webapp.py` / `python gui.py`  | No — just needs `ffmpeg` on your PATH. |
| `python desktop.py`                   | No — same. |
| `python build_exe.py` (frozen build)  | **Yes.** |

`runtime_paths.ffmpeg_exe()` uses the bundled copy when frozen and falls back to
`shutil.which("ffmpeg")` otherwise, so day-to-day development only needs ffmpeg
installed normally.

## Putting them back

Download a static Windows build (for example from
<https://www.gyan.dev/ffmpeg/builds/> or <https://github.com/BtbN/FFmpeg-Builds>),
then drop the two executables in here:

```
bin/ffmpeg.exe
bin/ffprobe.exe
```

On macOS/Linux the same applies without the `.exe` suffix.
