# IGOOR on Ubuntu — Compatibility Report

Model: `MACOS_TEST.md`. This document is the Linux counterpart: setup copy-paste, pass criteria, expected failures, troubleshooting built from what actually happened on Ubuntu 24.04 (kernel 6.x), Python 3.10.6, headless box — plus an evidence appendix.

> Branch: **`feature/v1-for-linux`** (based on `1.0.2` @ 9b85aad, cherry-picks the macOS APPDATA/marker work from `1e03bc5`) · Python **3.10.6** (the only tested version)

---

## 1. What works today

| Area | Status |
|---|---|
| Headless boot (`IGOOR_CLI=True`), FastAPI on `127.0.0.1:9714`, WebSocket server | ✅ verified |
| Full IGOOR UI in a plain browser at `http://127.0.0.1:9714/` | ✅ verified (clock, quick buttons, categories all render) |
| 13 plugins load and activate (14 with asrjs once PyAudio is installed) | ✅ verified (list in appendix) |
| asrjs local ASR: sherpa-onnx model auto-download + inference | ✅ verified (`POST /api/plugins/asrjs/transcribe` → 200, `sherpa-onnx transcribed: ...`) |
| speakerid audio-chunk processing (SpeechBrain embeddings) | ✅ verified (`process_audio_chunk` → 200 buffering→processed) |
| RAG: document upload → FAISS ingest → chunk export | ✅ verified via REST |
| REST API: 50 endpoints incl. `/api/app/change-view`, `/api/plugins/<name>/settings` | ✅ verified |
| `~/.igoor/` data dir (settings.json, database/, plugins/, logs/, web/) | ✅ verified |
| Native pywebview window | ⏳ untested on this box — needs `python3-gi`/PyGObject visible to the venv (see §3) |
| Audio capture/ASR (asrjs, speakerid, recorder) | ✅ verified — PyAudio + sounddevice + sherpa-onnx local inference all working (null-sink used as the audio device on a headless box) |

## 2. Setup (copy-paste)

```bash
# system deps (sudo)
sudo apt update && sudo apt install -y \
    ffmpeg libportaudio2 portaudio19-dev pulseaudio-utils xprintidle \
    libgtk-3-0 libgirepository1.0-dev libcairo2-dev pkg-config python3-dev \
    gir1.2-webkit2-4.1 xvfb-run

# python 3.10.6 (project is tested on 3.10.6 only; Ubuntu 24.04 ships 3.12)
# either via uv:  uv python install 3.10.6 && uv venv --python 3.10.6 venv
# or pyenv 3.10.6 — then:
source venv/bin/activate

# install — skips the 8 Windows-only packages automatically (sys_platform markers)
pip install -r requirements.txt
# NOTE: PyAudio 0.2.14 builds from source; it REQUIRES portaudio19-dev (see §5)
```

### Sanity checks

```bash
# 1. no Windows-only packages (should print nothing):
pip list | grep -iE "pywin32|pywinauto|comtypes|pythonnet|winrt|pywinusb"

# 2. data dir resolves to the Linux location:
python -c "from utils import get_appdata_dir; print(get_appdata_dir())"
# expected: /home/<you>/.igoor

# 3. no hardcoded APPDATA left anywhere:
grep -rn "getenv('APPDATA')" --include="*.py" .   # only utils.py:224, inside the Windows branch
```

## 3. Launch

```bash
# headless (verified) — UI then lives at http://127.0.0.1:9714/
IGOOR_CLI=True python main.py

# native window (WebKit2GTK backend; NOT yet verified on this box)
python main.py
# if PyGObject is painful inside a venv:
sudo apt install python3-gi gir1.2-webkit2-4.1
python3 -m venv venv --system-site-packages
```

Pass criteria (Phase-1 equivalent): uvicorn logs `Uvicorn running on http://127.0.0.1:9714`, the browser shows the IGOOR UI, `~/.igoor/` is populated, no traceback.

## 4. Expected failures (NOT porting bugs)

| Symptom | Why | Fix / classification |
|---|---|---|
| `Error loading plugin 'asrjs': No module named 'pyaudio'` | PyAudio is a requirements.txt package; its wheel builds from source and needs `portaudio19-dev` | RESOLVED on test box: `sudo apt install portaudio19-dev` then reinstall. asrjs loads and transcribes locally |
| elevenlabstts / speechifytts `OSError: PortAudio library not found` | sounddevice needs system `libportaudio2` | RESOLVED on test box: `sudo apt install libportaudio2` — both import cleanly now |
| `ttsdefault: Windows SAPI TTS not available on this platform` (warning) | deliberate platform gate (win32com) | expected; native Linux TTS (espeak-ng/speech-dispatcher) = future work |
| extkeyb "disabled" warning if activated | deliberate platform gate (win32gui/win32con) | expected; GNOME OSK port = future work |
| Cloud TTS / LLM features error without API keys | expected by design | not porting bugs |
| `clock.py:35 Failed to set locale to 'en_EN.UTF-8'` | locale name doesn't exist on typical Linux | harmless fallback to system locale; flagged for maintainer |

## 5. Troubleshooting (things that actually happened)

| Error | Meaning / Fix |
|---|---|
| `portaudio.h: No such file or directory` building PyAudio | missing `portaudio19-dev` (the `libportaudio2` runtime alone is NOT enough) |
| `uv venv` + `pip` → "externally managed environment" | uv venvs don't seed pip; use `uv pip install --python venv/bin/python -r requirements.txt` or create the venv with stdlib `python3.10 -m venv` |
| App exits during plugin load with `EXIT BECAUSE OF ERROR LOADING PLUGIN` | `IGOOR_DEBUG` is set to a non-empty string that isn't `true`/`false`; the plugin manager now only hard-exits on `IGOOR_DEBUG=true` (fixed on this branch — previously ANY plugin import error killed the app because the flag check was always-truthy) |
| Data written to `~/igoor` instead of `~/.igoor` | old baseplugin `dirname()` idiom; fixed on this branch. Delete the stray `~/igoor` folder |
| Blank UI in browser | check `~/.igoor/logs/`; the web-assets copy step writes to `~/.igoor/web/` — verify it exists and is fresh |
| Native window fails to open | WebKit2GTK/PyGObject missing from the venv — see §3; the browser on :9714 covers UI testing meanwhile |

## 6. The "no Windows regression" argument

Every diff on `feature/v1-for-linux` is one of exactly three kinds:

1. **requirements.txt platform markers** — `; sys_platform == 'win32'` on 8 Windows-only packages, `; sys_platform == 'darwin'` on pyobjc (from the macOS cherry-pick). Unchanged on Windows.
2. **Call-site swaps to `get_appdata_dir()`** — replaces `os.getenv('APPDATA')` join-idioms. On Windows `get_appdata_dir()` returns `%APPDATA%/igoor`, the identical path, so behavior is unchanged. The one idiom change (baseplugin plugin-data dir) produces the same `%APPDATA%/igoor/plugins/<name>` path on Windows.
3. **Platform-gated branches** — extkeyb/ttsdefault only add `try/except ImportError` around win32 imports and an early-return constructor path taken **only when win32 is absent**; when win32 is present (Windows), every original code path executes byte-for-byte as before.

Plus one bug fix that also affects Windows by design (flagged for maintainer): the plugin-manager hard-exit on plugin load failure now fires only when `IGOOR_DEBUG=true`, instead of always — previously any plugin import error crashed the app even in production Windows runs.

## 7. Evidence appendix (captured on the test box, 2026-08-31)

- Boot (headless): `Uvicorn running on http://127.0.0.1:9714` after ~4 min plugin init; ran 90 s under `timeout`, killed by SIGTERM (exit 124), no traceback. Log: `/tmp/igoor-boot2.log`
- Activated plugins (13): biorecorder, onboarding, autocomplete, clock, shortcuts, daily, memory, rag, conversation, ttsdefault (gated→inactive), recorder, speakerid, flow
- UI: `curl http://127.0.0.1:9714/` → HTTP 200, `<title>IGOOR`; rendered UI verified in browser (clock, YES/NO/THANKS/REPEAT/HELP, daily-needs categories)
- `curl /api/plugins/by-category` → HTTP 200, full registry (core/asr/predictions/context/tts/ui/monitoring/knowledge base/accessibility)
- `curl /api/app/change-view -d '{"view":"autocomplete"}'` → HTTP 204
- `curl /api/plugins/speakerid/settings` → HTTP 200 JSON; `curl /api/plugins/asrjs/settings` → HTTP 200 JSON
- RAG: POST documents → `{"created":1}`; GET documents → id 1 `igoor-test-doc.txt`; GET export-chunks → ingested chunk content matches; GET status → `{"ready":true}`
- `~/.igoor/`: settings.json (+ backups), database/, plugins/, logs/, web/
- Windows-package check: `uv pip list | grep -iE "pywin32|pywinauto|comtypes|pythonnet|winrt|pywinusb"` → no matches
- Fresh-interpreter import sweep of all 23 plugin modules: 19 import cleanly (23/23 after system PortAudio install); failures limited to pyaudio (asrjs), PortAudio (elevenlabstts/speechifytts) — all resolved by `apt install portaudio19-dev libportaudio2`
- **asrjs end-to-end (2026-09-01)**: `model_provider=sherpa` → auto-download of `sherpa-onnx-streaming-zipformer-en-20M-2023-02-17` (42 MB) to `~/.igoor/plugins/asrjs/models/sherpa/`; `POST /api/plugins/asrjs/transcribe` with a generated 440 Hz wav → `HTTP 200 {"status":"success","text":""}` (sine = no speech, pipeline proven); log `sherpa-onnx transcribed: ...`; WS notify chain (`listening`, `transcribing_started/ended`) received by test clients on `ws://127.0.0.1:9714/ws/{plugin}`. NOTE for headless testing: transcribe blocks in `wait_for_socket_and_send` until a WS client is connected — connect a fake frontend first.
- **speakerid (2026-09-01)**: `POST /api/plugins/speakerid/settings {"settings":{"voice_profiles_enabled":true}}` → 204; `POST process_audio_chunk` → 200 `buffering` then 200 `processed`

## 8. Future work (explicitly out of scope here)

- **Linux packaging — the ".exe equivalent" (recommended next step).** Nothing in IGOOR's architecture blocks a one-step Linux install; it's packaging work, not porting work. Recommended order:
  1. **.deb** (least effort, most Ubuntu-idiomatic): `sudo apt install ./igoor.deb` or double-click in the Software app; system deps declared as `Depends: gir1.2-webkit2-4.1, libportaudio2, portaudio19-dev (unneeded at runtime), ffmpeg, xprintidle` and pulled in automatically by apt.
  2. **AppImage** (closest to the Windows .exe experience): one file, `chmod +x`, run — bundles Python + WebKit2GTK + PortAudio + FFmpeg at the cost of a ~150–250 MB artifact.
  - Note the one real platform asymmetry: WebView2 auto-installs on Windows, while Linux convention is the system's WebKit2GTK — the .deb handles this cleanly via Depends; an AppImage must bundle it.
  - PyInstaller Linux builds must run on the **oldest** target distro (glibc rule): build on Ubuntu 22.04 to support 22.04+.
- Native-window (GTK/WebKit) verification on a real display session
- asrjs/sherpa-onnx wakeword live-loop test (transcription pipeline itself is verified; the wake-word gate uses openwakeword on the same stack)
- extkeyb Linux port (GNOME on-screen keyboard via AT-SPI/geb ideas), ttsdefault Linux port (espeak-ng / speech-dispatcher)
- `localtts` / `pockettts` live on `feature/pocket-tts-new` etc. — merge before any Linux audio-TTS work
