"""Generate the MSIX logo assets from the app icon.

Sizes referenced by AppxManifest.xml: Square44x44Logo (44x44),
Square150x150Logo (150x150), StoreLogo (50x50).

Run from the repo root with the project venv:
    venv/Scripts/python.exe installer/msix/make_icons.py
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "img", "logo_ig_lxL_icon.ico")
OUT = os.path.join(HERE, "assets")

SIZES = {
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
    "StoreLogo.png": 50,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    src = Image.open(SRC).convert("RGBA")
    for name, size in SIZES.items():
        icon = src.resize((size, size), Image.LANCZOS)
        path = os.path.join(OUT, name)
        icon.save(path)
        print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    main()
