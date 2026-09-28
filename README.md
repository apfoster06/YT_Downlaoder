# YT_downloader

A small command-line tool for downloading a video (or its audio) from YouTube
or any other site supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

It is built around a **two-phase workflow**: every run prints the video's
metadata (title, uploader, license, etc.) *first*, so you can confirm you have
the right to the content before anything is downloaded.

> **Rights are your responsibility.** Only download your own uploads,
> Creative Commons / public-domain material, or content you are otherwise
> licensed to use. Use `--inspect` to check the license field before pulling.

## Files

| File                 | Purpose                                              |
|----------------------|------------------------------------------------------|
| `download_video.py`  | The tool itself.                                     |
| `requirements.txt`   | Python dependency (`yt-dlp`).                         |
| `run.bat`            | Windows convenience launcher.                        |
| `downloads/`         | Default output folder (created on first download).   |

## Setup

```powershell
# from this folder
python -m pip install -r requirements.txt
```

You also need **ffmpeg** on your PATH (used to merge separate video+audio
streams and to extract mp3). Verify with:

```powershell
ffmpeg -version
```

## Usage

```powershell
# 1) Inspect — metadata only, NO download (use this to verify rights)
python download_video.py --inspect "https://youtu.be/XXXXXXXXXXX"

# 2) Download best quality into ./downloads
python download_video.py "https://youtu.be/XXXXXXXXXXX"

# 3) Cap the resolution
python download_video.py --max-height 720 "https://youtu.be/XXXXXXXXXXX"

# 4) Choose a different output folder
python download_video.py -o "D:/clips" "https://youtu.be/XXXXXXXXXXX"

# 5) Audio only, extracted to mp3
python download_video.py --audio "https://youtu.be/XXXXXXXXXXX"
```

Or via the launcher (passes all flags straight through):

```powershell
run.bat --inspect "https://youtu.be/XXXXXXXXXXX"
run.bat "https://youtu.be/XXXXXXXXXXX"
```

## Options

| Flag                 | Default       | Description                                   |
|----------------------|---------------|-----------------------------------------------|
| `url` (positional)   | —             | The video URL.                                |
| `--inspect`          | off           | Print metadata only; do not download.         |
| `-o`, `--output-dir` | `./downloads` | Folder to save into.                          |
| `--max-height`       | best          | Cap resolution, e.g. `1080`, `720`.           |
| `--audio`            | off           | Download audio only, extract to mp3.          |

## How it works

- Uses the **yt-dlp Python API** (`yt_dlp.YoutubeDL`) rather than shelling out.
- Prefers `mp4` video + `m4a` audio and merges to a clean `.mp4` via ffmpeg.
- `noplaylist=True` (one URL = one video) and `restrictfilenames=True`
  (filesystem-safe names) keep behaviour predictable on Windows.
- Retries and concurrent fragment downloads make large pulls more robust.
