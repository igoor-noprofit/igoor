# IGOOR on macOS — Boot Test

Goal: confirm the app **launches a window and boots** on macOS. This validates the `os.getenv('APPDATA')` → `get_appdata_dir()` migration (originally done on `feature/v1-for-mac`, now carried by the unified branch) **and** the plugin platform gating (`"platforms"` in plugin.json). It is *not* a full-feature test — expect audio plugins to fail on a remote Mac (no mic/speaker hardware).

> Branch: **`feature/v1-multiplatform`** (unified multiplatform branch; supersedes `feature/v1-for-mac`) · Target: **macOS, Apple Silicon (M-series) only** · Python **3.10.6**

⚠️ **Apple Silicon is required.** `torch==2.8.0` / `torchaudio==2.8.0` publish no Intel (x86_64) macOS wheels — `pip install` fails on Intel Macs with "no matching distribution". If you rent a remote Mac, it **must** be M-series.

---

## 1. Get a Mac (if you don't have one)

A remote macOS desktop is fine. Note that Apple licensing forces most providers to a **24-hour minimum billing** (see per-service notes below):

- **Scaleway M1 as-a-Service** — ~€0.10/hr, macOS desktop ready in ~5 min. ⚠️ **24-hour minimum lease** (Apple licensing), so even a quick test costs the ~€2.40 day floor: https://scaleway.com/en/hello-m1/
- **RentAMac.io** — flat ~$3.30/day (M4 Macs): https://rentamac.io/
- **MacinCloud** — hourly/daily pay-as-you-go: https://www.macincloud.com/ — ⚠️ they rent **both Intel and Apple Silicon** machines; pick an **M-series** plan (see the torch warning above)

⚠️ Browser-only services (BrowserStack, Browserling) **do not work** — IGOOR is a desktop app, not a website.

---

## 2. Setup

### The one-command way (recommended)

[`setup_mac.sh`](./setup_mac.sh) does everything below — **including installing Homebrew and the Xcode CLT if missing** (it checks each prerequisite first, so it's safe to re-run, and it's the easiest thing to hand to someone on a Mac). From any folder:

```bash
curl -fsSL https://raw.githubusercontent.com/igoor-noprofit/igoor/feature/v1-multiplatform/setup_mac.sh -o setup_mac.sh
bash setup_mac.sh
```

Useful variants:

```bash
IGOOR_BRANCH=macfix bash setup_mac.sh   # use a different branch
bash setup_mac.sh --run                 # setup + launch immediately
```

Each step prints its own duration estimate; expect **~15–30 min end-to-end**, almost all of it `pip install`. The script finishes with sanity checks (Windows packages skipped, pyobjc present, data dir resolves) and launch instructions.

### Manual steps (reference — what the script does)

```bash
# 0. Homebrew — NOT preinstalled (e.g. on rented Scaleway Macs):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# then add it to PATH (Apple Silicon) — the installer prints these same two lines at the end:
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# clone the unified multiplatform branch
git clone https://github.com/igoor-noprofit/igoor.git igoor && cd igoor
git checkout feature/v1-multiplatform

# system deps (audio libs + FFmpeg — needed by sounddevice/PyAudio/pydub)
brew install portaudio ffmpeg

# Python 3.10 — NOT preinstalled; Homebrew's default python is newer
brew install python@3.10

# PyAudio 0.2.14 builds from source on macOS — needs a compiler.
# Homebrew normally installs the CLT, but be explicit to avoid a confusing pip failure:
xcode-select --install   # no-op if already present

# optional (Homebrew Python only): tkinter for the splash screen.
# The app boots fine without it — you just skip the splash.
brew install python-tk@3.10

# python env
python3.10 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip

# install deps — should SKIP the 10 Windows-only packages and INSTALL the pyobjc stack
pip install -r requirements.txt
```

### Sanity check before launching

```bash
# 1. confirm Windows packages were skipped (these should ALL print nothing):
pip list | grep -iE "pywin32|pywinauto|comtypes|pythonnet|winrt"

# 2. confirm the macOS webview backend is present:
pip list | grep -i pyobjc          # expect the pyobjc stack (Cocoa, WebKit, Quartz, …) — pywebview pulls them all on darwin

# 3. confirm the data-dir helper resolves to the macOS location:
python -c "from utils import get_appdata_dir; print(get_appdata_dir())"
# expected: ~/Library/Application Support/igoor
```

---

## 3. Launch

```bash
python main.py
```

---

## 4. What "success" looks like (Phase 1 pass criteria)

- [ ] No `TypeError: expected str, bytes or os.PathLike object, not NoneType` (that was the APPDATA bug — it's gone)
- [ ] The **IGOOR splash/window opens** (pywebview via WKWebView)
- [ ] The local server is up: open `http://127.0.0.1:9714/` in Safari — should show the IGOOR UI
- [ ] `~/Library/Application Support/igoor/` got created with `settings.json`, `database/`, `plugins/`, `logs/`
- [ ] No Python traceback in the terminal on startup
- [ ] In Settings → Extensions, `ttsdefault` and `extkeyb` appear as disabled cards with **"Not available on this platform"** (this verifies the platform gate works end-to-end — their activation entries in settings.json must stay untouched)

**If you see a window open — Phase 1 passes.** That's the whole point of this test.

---

## 5. Expected failures (NOT blockers for Phase 1)

These are fine to ignore — they're Phase 2/3 work, already documented in `.factory/docs/2026-07-30-macos-porting-assessment.html`:

| Plugin | Symptom | Why |
|---|---|---|
| `ttsdefault` | disabled card "Not available on this platform" | Windows-only SAPI — **platform-gated** (never imported on Mac; a `say`/AVSpeech port is future work). TTS on Mac: use `pockettts` (local) or `elevenlabstts` / `speechifytts` (cloud) |
| `extkeyb` | disabled card "Not available on this platform" | Win32 keyboard automation — **platform-gated**; the `igoor` socket-keyboard mode is the cross-platform path |
| `asrjs` / TTS | mic/sound errors | remote Mac has no audio hardware |
| `bugreport` | black screenshot | needs Screen Recording permission (System Settings → Privacy) |
| `open sound settings` links | "Not supported on this platform" | `ms-settings:sound` is Windows-only; no macOS System Settings deep-link yet (non-fatal) |

---

## 6. Quick troubleshooting

| Error | Meaning / Fix |
|---|---|
| pip fails building **PyAudio** | missing compiler — run `xcode-select --install`, then retry |
| pip: **no matching distribution for torch/torchaudio** | you're on an **Intel Mac** — torch 2.8.0 has no x86_64 macOS wheels; switch to an Apple Silicon machine |
| app hard-exits (`os._exit`) on a plugin error | `IGOOR_DEBUG=true` makes any plugin load failure fatal — keep it unset for this test |
| `ModuleNotFoundError: win32com` / `win32gui` / `pywinauto` | should NOT happen anymore (gate + guarded imports) — if it does, note which plugin; it should be caught |
| `OSError: ... portaudio` | run `brew install portaudio` again |
| `pywebview` can't open a window | confirm the pyobjc stack installed (step 2 sanity check) |
| `FileNotFoundError: ffmpeg` | run `brew install ffmpeg` |
| Window opens but UI is blank | open Safari dev tools (or Safari → Develop); WKWebView caching differs from Edge — note the console errors |
| `TypeError: ... not NoneType` (APPDATA) | the migration didn't take — run `grep -rn "getenv('APPDATA')" *.py plugins/` and report what's left (the only valid hit is inside `utils.get_appdata_dir`) |

---

## 7. What to capture afterwards

If the boot works, grab these so the remaining work (macOS TTS port, `.dmg` packaging) has a baseline:

1. The **full startup log** from the terminal
2. A **screenshot** of the open window
3. `ls ~/Library/Application\ Support/igoor/` output
4. Any **console errors** from Safari/WebInspector on `127.0.0.1:9714`
5. Which plugins loaded vs failed (visible in the logs)

Paste these into a follow-up `.factory/docs/` note — they're the bridge from "it boots" to "it's shippable".
