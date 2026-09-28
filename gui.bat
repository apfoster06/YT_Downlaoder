@echo off
REM Double-click launcher for the YT Downloader GUI.
REM Uses pythonw so no console window lingers behind the app.

cd /d "%~dp0"
start "" pythonw "%~dp0gui.py"
