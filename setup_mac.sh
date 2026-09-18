#!/usr/bin/env bash
#
# IGOOR — one-command macOS setup
#
# Checks and installs everything IGOOR needs on a Mac (see MACOS_TEST.md):
# Homebrew, Xcode CLT, portaudio/ffmpeg/python@3.10, the repo, the venv and
# all Python dependencies. Every step checks before doing anything, so the
# script is SAFE TO RE-RUN (it only fills in what's missing).
#
# Usage:
#   bash setup_mac.sh             # full setup, then print launch instructions
#   bash setup_mac.sh --run       # full setup, then launch IGOOR
#
# Overridable via environment variables:
#   IGOOR_BRANCH   git branch     (default: feature/v1-multiplatform)
#   IGOOR_REPO     repo URL       (default: https://github.com/igoor-noprofit/igoor.git)
#   IGOOR_DIR      target folder  (default: ./igoor — ignored if run inside a checkout)
#
# Expected duration: ~15-30 min total, almost all of it pip (see step 6/7).
# Requirements: Apple Silicon Mac (M1/M2/M3/M4). Intel Macs cannot work:
# torch/torchaudio publish no x86_64 macOS wheels.

set -euo pipefail

REPO_URL="${IGOOR_REPO:-https://github.com/igoor-noprofit/igoor.git}"
BRANCH="${IGOOR_BRANCH:-feature/v1-multiplatform}"
TARGET_DIR="${IGOOR_DIR:-igoor}"
RUN_AFTER=0
[ "${1:-}" = "--run" ] && RUN_AFTER=1

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
info()  { printf '    %s\n' "$1"; }
ok()    { printf '    \033[32mOK\033[0m %s\n' "$1"; }
die()   { printf '    \033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

# ------------------------------------------------------------------ 1. hardware
step "1/7 · Hardware check"
ARCH="$(uname -m)"
[ "$ARCH" = "arm64" ] || die "Intel Mac ($ARCH) detected — IGOOR needs Apple Silicon (M-series)."
ok "Apple Silicon ($ARCH)"

# ------------------------------------------------------------------ 2. Homebrew
step "2/7 · Homebrew (checked first, installed only if missing)"
if command -v brew >/dev/null 2>&1; then
    ok "already installed: $(brew --version | head -1)"
else
    info "brew not found — installing (will ask for your macOS password, ~2-5 min)"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
# make brew reachable for this script even on a fresh shell, and for future shells
if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    grep -qs 'brew shellenv' ~/.zprofile || echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
fi
command -v brew >/dev/null 2>&1 || die "brew is still not available — install it from https://brew.sh, then re-run."
ok "brew on PATH: $(command -v brew)"

# ------------------------------------------------------------------ 3. Xcode CLT
step "3/7 · Xcode Command Line Tools (compiler needed to build PyAudio)"
if xcode-select -p >/dev/null 2>&1; then
    ok "already installed: $(xcode-select -p)"
else
    info "launching the installer — click Install in the dialog (~5-10 min)..."
    xcode-select --install || true
    printf '    Press ENTER here once the CLT installer has finished: '
    read -r < /dev/tty || true
    xcode-select -p >/dev/null 2>&1 || die "CLT still not installed. Run 'xcode-select --install', complete it, then re-run this script."
fi

# ------------------------------------------------------------------ 4. brew deps
step "4/7 · System dependencies (~1-3 min, prebuilt bottles)"
brew install portaudio ffmpeg python@3.10
ok "portaudio, ffmpeg, python@3.10 ready"
if brew install python-tk@3.10 2>/dev/null; then
    ok "python-tk installed (startup splash enabled)"
else
    info "python-tk@3.10 not available — fine, IGOOR just skips the splash screen."
fi

# ------------------------------------------------------------------ 5. source
step "5/7 · IGOOR source"
if [ -f "$(pwd)/main.py" ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    TARGET_DIR="$(pwd)"
    info "running inside an existing checkout ($TARGET_DIR) — leaving it as-is."
elif [ -d "$TARGET_DIR/.git" ]; then
    info "checkout exists at ./$TARGET_DIR — updating to latest '$BRANCH'"
    git -C "$TARGET_DIR" fetch --all --prune
    git -C "$TARGET_DIR" checkout "$BRANCH"
    git -C "$TARGET_DIR" pull --ff-only
else
    info "cloning '$BRANCH' into ./$TARGET_DIR ..."
    git clone -b "$BRANCH" "$REPO_URL" "$TARGET_DIR"
fi
[ -f "$TARGET_DIR/main.py" ] || die "$TARGET_DIR does not look like the IGOOR repo (main.py missing)."

# ------------------------------------------------------------------ 6. venv
step "6/7 · Python 3.10 venv + dependencies — THE LONG STEP (~10-15 min, ~2 GB download)"
PY310="$(command -v python3.10 || true)"
[ -n "$PY310" ] || PY310=/opt/homebrew/bin/python3.10
[ -x "$PY310" ] || die "python3.10 not found — did 'brew install python@3.10' succeed?"
if [ ! -x "$TARGET_DIR/venv/bin/python" ]; then
    "$PY310" -m venv "$TARGET_DIR/venv"
fi
PIP="$TARGET_DIR/venv/bin/pip"
PY="$TARGET_DIR/venv/bin/python"
"$PIP" install --upgrade pip >/dev/null
info "installing pinned dependencies — this is the slow part, grab a coffee..."
"$PIP" install -r "$TARGET_DIR/requirements.txt"
ok "python environment ready ($("$PY" --version))"

# ------------------------------------------------------------------ 7. sanity
step "7/7 · Sanity checks"
WIN_PKGS="$("$PIP" list 2>/dev/null | grep -iE 'pywin32|pywinauto|comtypes|pythonnet|winrt' || true)"
[ -z "$WIN_PKGS" ] || die "Windows-only packages ended up installed ($WIN_PKGS) — platform markers were ignored?"
"$PIP" show pyobjc-framework-Cocoa >/dev/null 2>&1 \
    && ok "pyobjc present (macOS webview backend)" \
    || die "pyobjc-framework-Cocoa is missing — run: venv/bin/pip install pyobjc-framework-Cocoa"
( cd "$TARGET_DIR" && "$PY" -c "from utils import get_appdata_dir; print('    OK data dir ->', get_appdata_dir())" )

# ------------------------------------------------------------------ done
printf '\n\033[1;32mSetup complete.\033[0m  (branch: %s, folder: %s)\n\n' "$BRANCH" "$TARGET_DIR"
cat <<EOF
Launch IGOOR (windowed):
    cd $TARGET_DIR && source venv/bin/activate && python main.py
Headless (no window — browse to http://127.0.0.1:9714):
    cd $TARGET_DIR && IGOOR_HEADLESS=true venv/bin/python main.py

First launch may download HuggingFace models (~1.15 GB) in the background.
Full test checklist (pass criteria, expected failures): MACOS_TEST.md
EOF

if [ "$RUN_AFTER" = "1" ]; then
    step "Launching IGOOR (--run)"
    cd "$TARGET_DIR"
    exec "$PY" main.py
fi
