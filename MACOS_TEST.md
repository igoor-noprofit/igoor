# IGOOR on macOS — Boot Test

Goal: confirm the app **launches a window and boots** on macOS. This validates the `os.getenv('APPDATA')` → `get_appdata_dir()` migration (originally done on `feature/v1-for-mac`, now carried by the unified branch) **and** the plugin platform gating (`"platforms"` in plugin.json). It is *not* a full-feature test — expect audio plugins to fail on a remote Mac (no mic/speaker hardware).

> Branch: **`feature/v1-multiplatform`** (unified multiplatform branch; supersedes `feature/v1-for-mac`) · Target: **macOS — Apple Silicon (M-series) and Intel** · Python **3.10.6**

**Both Mac architectures work.** Apple Silicon uses the main dependency set (torch 2.8.0). Intel macs get the Intel set automatically via `requirements.txt` markers: torch/torchaudio **2.2.2**, numpy < 2 (torch publishes no x86_64 macOS wheels after 2.2.2), and **no pocket-tts local neural TTS** — use `ttsmac` (macOS system voices) or cloud TTS there. Expect local AI features (ASR, embeddings) to run slower on Intel; for usable speed prefer cloud ASR (Whisper via Groq) and ttsmac/cloud TTS.

---

## 1. Get a Mac (if you don't have one)

A remote macOS desktop is fine. Note that Apple licensing forces most providers to a **24-hour minimum billing** (see per-service notes below):

- **Scaleway M1 as-a-Service** — ~€0.10/hr, macOS desktop ready in ~5 min. ⚠️ **24-hour minimum lease** (Apple licensing), so even a quick test costs the ~€2.40 day floor: https://scaleway.com/en/hello-m1/
- **RentAMac.io** — flat ~$3.30/day (M4 Macs): https://rentamac.io/
- **MacinCloud** — hourly/daily pay-as-you-go: https://www.macincloud.com/ — ⚠️ they rent **both Intel and Apple Silicon** machines; both work now (M-series is faster — pick it when in doubt)

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

# 0. Homebrew — NOT preinstalled (e.g. on rented Scaleway Macs):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# then add to PATH (Apple Silicon) — the installer prints these same two lines at the end:
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# system deps (audio libs + FFmpeg — needed by sounddevice/PyAudio/pydub)
# note: the brew installer above auto-installs the Xcode CLT, so xcode-select --install is already covered
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

### Intel Macs — what differs

Setup is identical (`setup_mac.sh` now accepts both architectures). Verify the
Intel dependency set resolved:

```bash
python -c "import platform, torch, numpy; print(platform.machine(), torch.__version__, numpy.__version__)"
# expected on Intel: x86_64 2.2.2 1.26.x   (Apple Silicon: arm64 2.8.0 2.2.x)
pip show pocket-tts                 # expect: NOT installed on Intel
```

Feature expectations on Intel:

- `ttsmac` (macOS system voices) and cloud TTS (`elevenlabstts` / `speechifytts`) work; the `pockettts` plugin loads but reports **not ready** ("pocket-tts is not installed") — that is the designed degradation, not a bug
- local ASR (sherpa-onnx) works but runs slower; prefer cloud ASR for responsiveness
- building the Intel .dmg for distribution is a build-machine task on Apple Silicon: `installer/dmg/build_dmg.sh --bootstrap-intel-venv` then `--arch x86_64` (see README)

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
| pip fails building **PyAudio** | missing compiler — run `xcode-select --install`, then retry (Intel macs also need `brew install portaudio`, which is x86_64 there) |
| pip: **no matching distribution for torch/torchaudio** | the arch markers were ignored or an old requirements.txt is in use — Intel macs must resolve torch 2.2.2; confirm with the Intel check above |
| app hard-exits (`os._exit`) on a plugin error | `IGOOR_DEBUG=true` makes any plugin load failure fatal — keep it unset for this test |
| `ModuleNotFoundError: win32com` / `win32gui` / `pywinauto` | should NOT happen anymore (gate + guarded imports) — if it does, note which plugin; it should be caught |
| `OSError: ... portaudio` | run `brew install portaudio` again |
| `pywebview` can't open a window | confirm the pyobjc stack installed (step 2 sanity check) |
| `FileNotFoundError: ffmpeg` | run `brew install ffmpeg` |
| Window opens but UI is blank | open Safari dev tools (or Safari → Develop); WKWebView caching differs from Edge — note the console errors |
| `TypeError: ... not NoneType` (APPDATA) | the migration didn't take — run `grep -rn "getenv('APPDATA')" *.py plugins/` and report what's left (the only valid hit is inside `utils.get_appdata_dir`) |

---

## 7. What to capture afterwards

If the boot works, grab these so the remaining work (macOS TTS port) has a baseline:
(`.dmg` packaging now exists: `installer/dmg/build_dmg.sh` — see
[docs/distribution.md](docs/distribution.md#macos-distribution-strategy).)

1. The **full startup log** from the terminal
2. A **screenshot** of the open window
3. `ls ~/Library/Application\ Support/igoor/` output
4. Any **console errors** from Safari/WebInspector on `127.0.0.1:9714`
5. Which plugins loaded vs failed (visible in the logs)

Paste these into a follow-up `.factory/docs/` note — they're the bridge from "it boots" to "it's shippable".
