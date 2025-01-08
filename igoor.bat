@echo off
call venv\scripts\activate
set PYTHONW=1
set "IGOOR_FULLSCREEN=True"
set "IGOOR_DEBUG=False"
start /B pythonw main.py