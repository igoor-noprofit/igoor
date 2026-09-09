"""Generate the macOS app icon (img/igoor.icns) from the app .ico.

Builds an Apple iconset (16 -> 512@2x) from the largest frame of
img/igoor_logo_pLG_icon.ico (256x256, the highest-resolution source in
the repo, same family as the MSIX assets) and converts it with
`iconutil -c icns` (ships with macOS, no brew deps).

Run from the repo root with the project venv:
    venv/bin/python installer/dmg/make_icns.py
"""
import os
import subprocess

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "img", "igoor_logo_pLG_icon.ico")
ICONSET = os.path.join(HERE, "IGOOR.iconset")
OUT = os.path.join(HERE, "..", "..", "img", "igoor.icns")

# iconset filename -> render size in px
SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def main():
    src = Image.open(SRC).convert("RGBA")
    os.makedirs(ICONSET, exist_ok=True)
    for name, size in SIZES.items():
        src.resize((size, size), Image.LANCZOS).save(os.path.join(ICONSET, name))
    subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", OUT], check=True)
    subprocess.run(["rm", "-rf", ICONSET], check=True)
    print(f"Created {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
