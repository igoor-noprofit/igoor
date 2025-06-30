@echo off
copy /Y igoor.spec.txt igoor.spec
pyinstaller igoor.spec --noconfirm