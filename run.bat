@echo off
REM Convenience launcher for download_video.py
REM Usage:  run.bat "https://youtu.be/XXXX"  [extra yt-dlp flags]
REM   run.bat --inspect "https://youtu.be/XXXX"     (metadata only, no download)
REM   run.bat "https://youtu.be/XXXX"               (download best quality)
REM   run.bat --audio "https://youtu.be/XXXX"       (audio-only -> mp3)

cd /d "%~dp0"
python "%~dp0download_video.py" %*
