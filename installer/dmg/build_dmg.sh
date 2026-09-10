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
#   installer/dmg/build_dmg.sh [--upload-release]
#
# Apple Silicon only (torch 2.8.0 has no macOS x86_64 wheels).
# ========================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

VENV_PY="$ROOT/venv/bin/python"
DIST_APP="$ROOT/dist/IGOOR.app"
UPLOAD_RELEASE=0
[[ "${1:-}" == "--upload-release" ]] && UPLOAD_RELEASE=1

log() { echo "[build_dmg] $*"; }
die() { echo "[build_dmg] ERROR: $*" >&2; exit 1; }

# --- 1. Preflight ------------------------------------------------------------
[[ -x "$VENV_PY" ]] || die "venv python not found at $VENV_PY (see setup_mac.sh)"
"$VENV_PY" -c "import PyInstaller" 2>/dev/null || die "PyInstaller not installed in venv (pip install -r requirements.txt)"

VERSION="$("$VENV_PY" -c "import re; print(re.search(r\"__version__\s*=\s*['\\\"]([^'\\\"]+)\", open('version.py').read()).group(1))")"
[[ -n "$VERSION" ]] || die "could not parse __version__ from version.py"
DMG="$ROOT/dist/IGOOR-$VERSION-mac-arm64.dmg"

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
log "running PyInstaller (several minutes for ~1.2 GB)..."
"$VENV_PY" -m PyInstaller igoor.spec --noconfirm
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
  ASSET_NAME="IGOOR-$VERSION-mac-arm64.dmg"
  log "uploading $ASSET_NAME to $REPO release $TAG..."
  RELEASE_ID="$(curl -s -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"tag_name\":\"$TAG\",\"target_commitish\":\"$(git rev-parse --abbrev-ref HEAD)\"}" \
    "https://api.github.com/repos/$REPO/releases" | $VENV_PY -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"
  [[ -n "$RELEASE_ID" ]] || die "could not create GitHub release"
  curl -s -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/octet-stream" \
    -T "$DMG" \
    "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$ASSET_NAME" > /dev/null
  log "uploaded to release $TAG (id $RELEASE_ID)"
fi

log "DONE: $DMG"
