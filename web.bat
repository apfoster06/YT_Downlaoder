@echo off
REM Launch the local YT Downloader website, then open it in the browser.
REM Stop the server with Ctrl+C in this window.

cd /d "%~dp0"
start "" http://127.0.0.1:8093
python "%~dp0webapp.py"
