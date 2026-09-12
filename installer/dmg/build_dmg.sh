#!/usr/bin/env bash
# ========================================
# Build the macOS IGOOR .app and package it as a .dmg.
#
# The macOS counterpart of installer/msix/build_msix.bat, including the
# orchestrator role create_installable.bat plays on Windows:
#   1. venv / pyinstaller checks, version from version.py
#   2. .env swap (ship production flags, not the repo dev ones)
#   3. pyinstaller igoor.spec (copied from igoor.spec.txt, like the .bat flow)
#   4. codesign (Developer ID from $IGOOR_CODESIGN_IDENTITY, else ad-hoc)
#   5. DMG via hdiutil (IGOOR.app + Applications symlink, no brew deps)
#   6. Optional notarization: set IGOOR_NOTARY_PROFILE (xcrun notarytool
#      store-credentials) to submit + staple
#   7. Optional GitHub release upload: --upload-release with .github_token.txt
#
# Usage:
#   installer/dmg/build_dmg.sh [--arch arm64|x86_64] [--bootstrap-intel-venv]
#                              [--upload-release]
#
# Dual-arch: arm64 builds from the `venv`, Intel (x86_64) builds from
# `venv-intel` (created under Rosetta 2 by --bootstrap-intel-venv; torch
# 2.2.2 via requirements.txt markers — 2.3.0+ has no x86_64 macOS wheels).
# ========================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

UPLOAD_RELEASE=0
BOOTSTRAP_INTEL=0
TARGET_ARCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --upload-release) UPLOAD_RELEASE=1 ;;
    --bootstrap-intel-venv) BOOTSTRAP_INTEL=1 ;;
    --arch) TARGET_ARCH="${2:?--arch needs a value (arm64|x86_64)}"; shift ;;
    --arch=*) TARGET_ARCH="${1#--arch=}" ;;
    *) echo "[build_dmg] ERROR: unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

log() { echo "[build_dmg] $*"; }
die() { echo "[build_dmg] ERROR: $*" >&2; exit 1; }

# --- 1a. Optional one-time bootstrap of the Intel (x86_64) build venv --------
# Idempotent: every step checks before doing anything, so re-running fills in
# only what is missing. Needs an x86_64-capable python3.10 (python.org
# universal2 installer, or Rosetta Homebrew's python@3.10 at /usr/local).
# PyAudio has no wheels: it builds from source and links x86_64 portaudio,
# which is why the Rosetta Homebrew step exists.
find_x86_64_py310() {
  local candidate
  for candidate in \
      "$(command -v python3.10 2>/dev/null || true)" \
      /usr/local/bin/python3.10 \
      /Library/Frameworks/Python.framework/Versions/3.10/bin/python3; do
    [[ -x "$candidate" ]] || continue
    # python.org python is universal2: verify the x86_64 slice really runs
    [[ "$(arch -x86_64 "$candidate" -c 'import platform; print(platform.machine())' 2>/dev/null)" == "x86_64" ]] || continue
    echo "$candidate"
    return 0
  done
  return 1
}

bootstrap_intel_venv() {
  log "bootstrap-intel-venv: Rosetta setup for the Intel (x86_64) build"
  if ! arch -x86_64 /usr/bin/true 2>/dev/null; then
    log "installing Rosetta 2 (asks for your password once)..."
    softwareupdate --install-rosetta --agree-to-license || die "could not install Rosetta 2"
  else
    log "Rosetta 2 already present"
  fi

  local PY310_SRC=""
  if PY310_SRC="$(find_x86_64_py310)"; then
    log "x86_64-capable python3.10: $PY310_SRC"
  elif [[ ! -x /usr/local/bin/brew ]]; then
    die "no x86_64-capable python3.10 found. Install the python.org universal2 Python 3.10 (runs its x86_64 slice under Rosetta), then re-run."
  fi

  if [[ ! -x /usr/local/bin/brew ]]; then
    log "installing Rosetta Homebrew into /usr/local (x86_64 portaudio for PyAudio)..."
    arch -x86_64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
      || die "Rosetta Homebrew install failed (install it manually, then re-run)"
  fi
  if [[ -x /usr/local/bin/brew ]]; then
    # python@3.10 too: on a fresh M-series build machine this is the only
    # x86_64-capable python3.10 the bootstrap can build venv-intel from.
    arch -x86_64 /usr/local/bin/brew list --formula portaudio ffmpeg python@3.10 >/dev/null 2>&1 \
      || arch -x86_64 /usr/local/bin/brew install portaudio ffmpeg python@3.10
    log "x86_64 portaudio/ffmpeg/python@3.10 ready (/usr/local)"
  fi

  if [[ ! -x "$ROOT/venv-intel/bin/python" ]]; then
    [[ -n "$PY310_SRC" ]] || PY310_SRC="$(find_x86_64_py310)" || die "no x86_64-capable python3.10 found (see above)"
    log "creating venv-intel (x86_64 under Rosetta)..."
    arch -x86_64 "$PY310_SRC" -m venv "$ROOT/venv-intel"
  fi
  log "upgrading pip + installing requirements into venv-intel (this is the wheel-gap detector — PyAudio needs the /usr/local portaudio installed above)..."
  arch -x86_64 "$ROOT/venv-intel/bin/python" -m pip install --upgrade pip
  arch -x86_64 "$ROOT/venv-intel/bin/pip" install -r "$ROOT/requirements.txt"
  log "venv-intel ready"
}

# --- 1b. Venv selection --------------------------------------------------------
# Arch -> venv map: arm64 -> venv, x86_64 -> venv-intel. IGOOR_VENV overrides.
if [[ "$BOOTSTRAP_INTEL" == 1 ]]; then
  bootstrap_intel_venv
fi

pick_venv() {
  if [[ -n "${IGOOR_VENV:-}" ]]; then
    echo "$ROOT/$IGOOR_VENV"
  elif [[ -n "$TARGET_ARCH" ]]; then
    [[ "$TARGET_ARCH" == "arm64" ]] && echo "$ROOT/venv" || echo "$ROOT/venv-intel"
  elif [[ -x "$ROOT/venv/bin/python" ]]; then
    echo "$ROOT/venv"
  else
    echo "$ROOT/venv-intel"
  fi
}
VENV="$(pick_venv)"
VENV_PY="$VENV/bin/python"
[[ -x "$VENV_PY" ]] || die "venv python not found at $VENV_PY (arm64: setup_mac.sh; x86_64: build_dmg.sh --bootstrap-intel-venv)"
"$VENV_PY" -c "import PyInstaller" 2>/dev/null || die "PyInstaller not installed in $VENV (pip install -r requirements.txt)"

# The venv must actually run in the requested architecture. A universal2
# interpreter (python.org 3.10) would otherwise run its arm64 slice on an
# Apple Silicon host and silently produce wrong-arch wheels/executables.
VENV_ARCH="$("$VENV_PY" -c "import platform; print(platform.machine())")"
if [[ -n "$TARGET_ARCH" && "$VENV_ARCH" != "$TARGET_ARCH" ]]; then
  die "$VENV runs as $VENV_ARCH but --arch $TARGET_ARCH was requested (bootstrap the right venv: build_dmg.sh --bootstrap-intel-venv)"
fi
run_venv_py() {
  if [[ "$VENV_ARCH" == "x86_64" && "$(uname -m)" != "x86_64" ]]; then
    arch -x86_64 "$VENV_PY" "$@"
  else
    "$VENV_PY" "$@"
  fi
}

VERSION="$(run_venv_py -c "import re; print(re.search(r\"__version__\s*=\s*['\\\"]([^'\\\"]+)\", open('version.py').read()).group(1))")"
[[ -n "$VERSION" ]] || die "could not parse __version__ from version.py"
DMG="$ROOT/dist/IGOOR-$VERSION-mac-$VENV_ARCH.dmg"
DIST_APP="$ROOT/dist/IGOOR.app"

SIGN_IDENTITY="${IGOOR_CODESIGN_IDENTITY:-}"
NOTARY_PROFILE="${IGOOR_NOTARY_PROFILE:-}"

# --- 2. .env swap: ship production flags, not the repo dev ones --------------
# Same trick as build_msix.bat: the repo .env (when present) carries dev flags
# (headless/external access/debug). Stash it, bundle env.production, restore.
# The repo may legitimately have no .env at all (it is gitignored) - then just
# ship env.production and remove the copy afterwards.
# Keyed on the stash file's existence so the trap is idempotent and safe on
# every exit path: stash present -> the user had a dev .env (put it back);
# absent -> we created the production copy (remove it). The restore happens
# only in the EXIT trap - no early call, so there is no flag to reset.
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

# --- 3. PyInstaller -----------------------------------------------------------
cp "$ROOT/igoor.spec.txt" "$ROOT/igoor.spec"
log "running PyInstaller (several minutes for ~1.2 GB, arch $VENV_ARCH)..."
run_venv_py -m PyInstaller igoor.spec --noconfirm
rm -f "$ROOT/igoor.spec"
[[ -d "$DIST_APP" ]] || die "dist/IGOOR.app not produced"

# --- 4. codesign --------------------------------------------------------------
# Order matters: sign innermost binaries first, then the .app. --deep handles
# the tree, then we re-sign the app root with runtime options + entitlements.
if [[ -n "$SIGN_IDENTITY" ]]; then
  log "signing with identity: $SIGN_IDENTITY (hardened runtime)"
  codesign --force --deep --sign "$SIGN_IDENTITY" "$DIST_APP"
  codesign --force --sign "$SIGN_IDENTITY" --options runtime \
    --entitlements "$HERE/entitlements.plist" "$DIST_APP"
else
  log "no IGOOR_CODESIGN_IDENTITY set - ad-hoc signing (test builds only)"
  codesign --force --deep --sign - "$DIST_APP"
fi
codesign --verify --deep --strict "$DIST_APP" || die "codesign verification failed"
log "codesign verified"

# --- 5. DMG --------------------------------------------------------------------
mkdir -p "$ROOT/dist"
rm -f "$DMG"
DMGROOT="$(mktemp -d)/dmg"
mkdir -p "$DMGROOT"
cp -R "$DIST_APP" "$DMGROOT/IGOOR.app"
ln -s /Applications "$DMGROOT/Applications"
log "creating DMG with hdiutil..."
hdiutil create -volname "IGOOR" -srcfolder "$DMGROOT" -ov -format UDZO "$DMG"
log "created: $DMG"

# --- 6. Notarization (optional) -------------------------------------------------
if [[ -n "$NOTARY_PROFILE" ]]; then
  log "notarizing with profile: $NOTARY_PROFILE (can take ~15 min)..."
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DIST_APP"
  xcrun stapler staple "$DMG"
  spctl -a -t exec "$DIST_APP/Contents/MacOS/igoor" || true
  log "notarized and stapled"
else
  log "IGOOR_NOTARY_PROFILE not set - skipping notarization (unsigned DMG: testers must right-click -> Open)"
fi

# --- 7. GitHub release upload (optional) ------------------------------------------
if [[ "$UPLOAD_RELEASE" == 1 ]]; then
  TOKEN="$(cat "$ROOT/.github_token.txt" 2>/dev/null || true)"
  [[ -n "$TOKEN" ]] || die "--upload-release given but .github_token.txt missing"
  REPO="igoor-noprofit/igoor"
  TAG="v$VERSION"
  ASSET_NAME="IGOOR-$VERSION-mac-$VENV_ARCH.dmg"
  log "uploading $ASSET_NAME to $REPO release $TAG..."
  # Look up an existing release for the tag first: the create-POST returns
  # 422 already_exists when the release is already there (e.g. when uploading
  # the second arch's DMG to the same release), which yields no id.
  RELEASE_ID="$(curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$REPO/releases/tags/$TAG" | $VENV_PY -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"
  if [[ -z "$RELEASE_ID" ]]; then
    RELEASE_ID="$(curl -s -X POST \
      -H "Authorization: token $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"tag_name\":\"$TAG\",\"target_commitish\":\"$(git rev-parse --abbrev-ref HEAD)\"}" \
      "https://api.github.com/repos/$REPO/releases" | $VENV_PY -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"
  fi
  [[ -n "$RELEASE_ID" ]] || die "could not create GitHub release"
  # Replace a same-named asset so re-running the upload stays idempotent
  ASSET_ID="$(curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$REPO/releases/$RELEASE_ID/assets" | $VENV_PY -c "import json,sys; print(next((a['id'] for a in json.load(sys.stdin) if a['name']=='$ASSET_NAME'), ''))")"
  if [[ -n "$ASSET_ID" ]]; then
    log "asset $ASSET_NAME already exists - replacing it"
    curl -s -X DELETE -H "Authorization: token $TOKEN" \
      "https://api.github.com/repos/$REPO/releases/assets/$ASSET_ID" > /dev/null
  fi
  curl -s -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/octet-stream" \
    -T "$DMG" \
    "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$ASSET_NAME" > /dev/null
  log "uploaded to release $TAG (id $RELEASE_ID)"
fi

log "DONE: $DMG"
