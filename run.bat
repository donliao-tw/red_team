@echo off
cd /d "%~dp0"
python flasher\main.py
if errorlevel 1 pause
