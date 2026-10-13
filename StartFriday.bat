@echo off
cd /d "%~dp0"
call .\.venv313\Scripts\activate.bat
python friday_launcher.py
pause
