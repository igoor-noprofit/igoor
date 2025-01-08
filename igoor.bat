@echo off
call venv\scripts\activate
set PYTHONW=1
set "IGOOR_FULLSCREEN=True"
start /B pythonw main.py