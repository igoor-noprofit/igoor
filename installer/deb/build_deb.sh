#!/usr/bin/env bash
# ========================================
# Build the Linux IGOOR .deb package.
#
# The Linux counterpart of installer/msix/build_msix.bat (Windows) and
# installer/dmg/build_dmg.sh (macOS), same orchestrator flow:
#   1. venv / pyinstaller checks, version from version.py
#   2. .env swap (ship production flags, not the repo dev ones)
#   3. pyinstaller igoor.spec (copied from igoor.spec.txt, like the .bat flow)
#   4. .deb via dpkg-deb (no extra tools; icon extracted from the .ico)
#   5. Optional GitHub release upload: --upload-release with .github_token.txt
#
# Usage:
#   installer/deb/build_deb.sh [--upload-release]
#
# Build on the OLDEST distro you want to support (glibc rule): build on
# Ubuntu 22.04 → runs on 22.04+. System deps the packaged app needs at runtime
# are declared in control/ Depends (apt pulls them in on install).
# ========================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

VENV_PY="$ROOT/venv/bin/python"
DIST_APP="$ROOT/dist/igoor"
UPLOAD_RELEASE=0
[[ "${1:-}" == "--upload-release" ]] && UPLOAD_RELEASE=1

log() { echo "[build_deb] $*"; }
die() { echo "[build_deb] ERROR: $*" >&2; exit 1; }

# --- 1. Preflight ------------------------------------------------------------
[[ -x "$VENV_PY" ]] || die "venv python not found at $VENV_PY (see COMPAT_UBUNTU.md §2)"
"$VENV_PY" -c "import PyInstaller" 2>/dev/null || die "PyInstaller not installed in venv (pip install -r requirements.txt)"
command -v dpkg-deb >/dev/null || die "dpkg-deb not found (apt install dpkg-dev)"

# CPU-only torch guard: igoor.spec.txt strips nvidia/ and triton/ binaries from
# the bundle, so a CUDA-flavored torch in the venv would freeze a broken import
# (libtorch_cuda.so links against the stripped libs). The venv must use the
# +cpu wheels; verify before wasting a multi-minute PyInstaller run.
"$VENV_PY" -c "import torch, importlib.util as u; assert torch.version.cuda is None and u.find_spec('triton') is None"   || die "build venv torch is CUDA-flavored (or broken) - install the +cpu wheels first:
     pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu"
log "torch: CPU-only build confirmed"

VERSION="$("$VENV_PY" -c "import re; print(re.search(r\"__version__\s*=\s*['\\\"]([^'\\\"]+)\", open('version.py').read()).group(1))")"
[[ -n "$VERSION" ]] || die "could not parse __version__ from version.py"
DEB="$ROOT/dist/igoor_$VERSION-1_amd64.deb"

# --- 2. .env swap: ship production flags, not the repo dev ones ---------------
# Same trick as build_msix.bat / build_dmg.sh: the repo .env (when present)
# carries dev flags (headless/external access/debug). Stash it, bundle
# env.production, restore on exit.
restore_env() {
  if [[ -f "$ROOT/.env.stashed" ]]; then
    mv "$ROOT/.env.stashed" "$ROOT/.env"
  else
    rm -f "$ROOT/.env"
  fi
}
trap restore_env EXIT
if [[ -f "$ROOT/.env" ]]; then
  mv "$ROOT/.env" "$ROOT/.env.stashed"
fi
cp "$HERE/../msix/env.production" "$ROOT/.env"
log "shipping production .env"

# --- 3. PyInstaller ------------------------------------------------------------
cp "$ROOT/igoor.spec.txt" "$ROOT/igoor.spec"
log "running PyInstaller (several minutes for ~1.5 GB)..."
"$VENV_PY" -m PyInstaller igoor.spec --noconfirm
rm -f "$ROOT/igoor.spec"
[[ -d "$DIST_APP" ]] || die "dist/igoor not produced"

# --- 4. .deb --------------------------------------------------------------------
# Layout: PyInstaller's onedir output lands under /opt/igoor (self-contained:
# no /usr/lib pollution, mirrors Program Files on Windows). The launcher in
# /usr/bin is a shim so 'igoor' works from any terminal. Icon: the .ico already
# ships in the bundle; extract a 256px PNG once for the .desktop file.
PKGROOT="$(mktemp -d)"
trap 'rm -rf "$PKGROOT"; restore_env' EXIT

INSTALL_DIR="/opt/igoor"
mkdir -p "$PKGROOT$INSTALL_DIR" "$PKGROOT/usr/bin" "$PKGROOT/usr/share/applications" "$PKGROOT/usr/share/icons/hicolor/256x256/apps"

log "copying PyInstaller output (~1.5 GB)..."
cp -R "$DIST_APP/." "$PKGROOT$INSTALL_DIR/"

cat > "$PKGROOT/usr/bin/igoor" <<'LAUNCHER'
#!/bin/sh
# IGOOR launcher shim — the real app is /opt/igoor/igoor
cd /opt/igoor
exec ./igoor "$@"
LAUNCHER
chmod 755 "$PKGROOT/usr/bin/igoor"

"$VENV_PY" - "$ROOT" "$PKGROOT/usr/share/icons/hicolor/256x256/apps/igoor.png" <<'ICON'
import sys
from PIL import Image
root, out = sys.argv[1], sys.argv[2]
ico = f"{root}/img/igoor_logo_pLG_icon.ico"
im = Image.open(ico)
# pick the largest square frame, or the largest frame resized to 256x256
frames = []
for i in range(getattr(im, 'n_frames', 1)):
    im.seek(i)
    if im.size[0] == im.size[1]:
        frames.append((im.size[0], im.copy()))
if not frames:  # no square frame (wordmark .ico): pad the largest one
    im.seek(0)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    frames = [(side, canvas)]
side, best = max(frames, key=lambda t: t[0])
best = best.convert('RGBA').resize((256, 256), Image.LANCZOS)
best.save(out)
print('icon written:', out)
ICON
[[ -f "$PKGROOT/usr/share/icons/hicolor/256x256/apps/igoor.png" ]] || die "icon extraction failed"

cat > "$PKGROOT/usr/share/applications/igoor.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=IGOOR
GenericName=Conversational aid
Comment=Conversational application controllable via eye-tracking, for people with neurodegenerative diseases or paralysis
Exec=igoor %f
Icon=igoor
Terminal=false
Categories=Accessibility;Utility;
StartupWMClass=igoor
DESKTOP

mkdir -p "$PKGROOT/DEBIAN"
cat > "$PKGROOT/DEBIAN/control" <<CONTROL
Package: igoor
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: gir1.2-webkit2-4.1, libportaudio2, ffmpeg, xprintidle
Recommends: pulseaudio-utils
Maintainer: IGOOR not-for-profit organization <contact@igoor.org>
Description: IGOOR — conversational aid controllable via eye-tracking
 Free open-source conversational application based on AI, designed to provide
 people with ALS/MND diseases a smooth and natural means of communication.
 Its interface is easy to use via eye-tracking devices.
Homepage: https://igoor.org
CONTROL

log "building .deb with dpkg-deb..."
mkdir -p "$ROOT/dist"
rm -f "$DEB"
fakeroot dpkg-deb --build --root-owner-group "$PKGROOT" "$DEB" 2>/dev/null \
  || dpkg-deb --build --root-owner-group "$PKGROOT" "$DEB" \
  || die "dpkg-deb failed (install fakeroot or run with sufficient privileges)"
log "created: $DEB"

# --- 5. Optional release upload -------------------------------------------------
# (kept minimal for the draft; wire to the same gh-release flow as build_dmg.sh
#  when the CI conversation lands)
if [[ $UPLOAD_RELEASE -eq 1 ]]; then
  die "--upload-release not wired yet (see build_dmg.sh §7 for the pattern)"
fi

log "done. Install with: sudo apt install ./$(basename "$DEB")"
