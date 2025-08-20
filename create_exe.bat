@echo off
copy /Y igoor.spec.txt igoor.spec
rmdir /s /q build
rmdir /s /q dist
pyinstaller igoor.spec
pyinstaller igoor.spec --noconfirm