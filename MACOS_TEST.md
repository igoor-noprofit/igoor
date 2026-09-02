# IGOOR on macOS — Phase 1 Boot Test

Goal: confirm the app **launches a window and boots** on macOS. This validates the `os.getenv('APPDATA')` → `get_appdata_dir()` migration (originally done on `feature/v1-for-mac`, now carried by the unified branch). It is *not* a full-feature test — expect audio plugins to fail on a remote Mac (no mic/speaker hardware).

> Branch: **`feature/v1-multiplatform`** (unified multiplatform branch; supersedes `feature/v1-for-mac`) · Target: **macOS** (Apple Silicon or Intel) · Python **3.10.6**

---

## 1. Get a Mac (if you don't have one)

A remote macOS desktop is fine. Pick one with **per-minute/hourly** billing so a smoke test costs ~$1–2:

- **Scaleway M1 as-a-Service** — per-minute, best for a quick session: https://scaleway.com/en/hello-m1/
- **RentAMac.io** — flat ~$3.30/day: https://rentamac.io/
- **MacinCloud** — hourly/daily pay-as-you-go: https://www.macincloud.com/

⚠️ Browser-only services (BrowserStack, Browserling) **do not work** — IGOOR is a desktop app, not a website.

---

## 2. Setup (copy-paste)

```bash
# clone the unified multiplatform branch
git clone https://github.com/igoor-noprofit/igoor.git igoor && cd igoor
git checkout feature/v1-multiplatform

# system deps (audio libs + FFmpeg — needed by sounddevice/PyAudio/pydub)
brew install portaudio ffmpeg

# python env
python3.10 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip

# install deps — should SKIP the 8 Windows-only packages and INSTALL pyobjc
pip install -r requirements.txt
```

### Sanity check before launching

```bash
# 1. confirm Windows packages were skipped (these should ALL print nothing):
pip list | grep -iE "pywin32|pywinauto|comtypes|pythonnet|winrt"

# 2. confirm the macOS webview backend is present:
pip list | grep -i pyobjc          # expect: pyobjc-framework-Cocoa (+ core deps)

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

**If you see a window open — Phase 1 passes.** That's the whole point of this test.

---

## 5. Expected failures (NOT blockers for Phase 1)

These are fine to ignore — they're Phase 2/3 work, already documented in `.factory/docs/2026-07-30-macos-porting-assessment.html`:

| Plugin | Symptom | Why |
|---|---|---|
| `ttsdefault` | fails to load | Windows SAPI not on Mac → needs `say`/AVSpeech port |
| `extkeyb` | fails to load | Win32 keyboard automation → needs gating |
| `asrjs` / TTS | mic/sound errors | remote Mac has no audio hardware |
| `bugreport` | black screenshot | needs Screen Recording permission (System Settings → Privacy) |

---

## 6. Quick troubleshooting

| Error | Meaning / Fix |
|---|---|
| `ModuleNotFoundError: win32com` / `win32gui` / `pywinauto` | a plugin importing a Windows-only module — expected; it should be caught, but if it crashes the app, note which plugin |
| `OSError: ... portaudio` | run `brew install portaudio` again |
| `pywebview` can't open a window | confirm `pyobjc-framework-Cocoa` installed (step 2 sanity check) |
| `FileNotFoundError: ffmpeg` | run `brew install ffmpeg` |
| Window opens but UI is blank | open Safari dev tools (or Safari → Develop); WKWebView caching differs from Edge — note the console errors |
| `TypeError: ... not NoneType` (APPDATA) | the migration didn't take — run `grep -rn "getenv('APPDATA')" *.py plugins/` and report what's left |

---

## 7. What to capture for Phase 2

If the boot works, grab these so the next phases (plugin ports, `.dmg` packaging) have a baseline:

1. The **full startup log** from the terminal
2. A **screenshot** of the open window
3. `ls ~/Library/Application\ Support/igoor/` output
4. Any **console errors** from Safari/WebInspector on `127.0.0.1:9714`
5. Which plugins loaded vs failed (visible in the logs)

Paste these into a follow-up `.factory/docs/` note — they're the bridge from "it boots" to "it's shippable".
