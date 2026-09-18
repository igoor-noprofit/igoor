# plan.md — IGOOR macOS Verification: Execution Plan & Status

> Companion to `soul.md` (identity, laws, ground truth — read that first).
> This file is **state**: tick boxes, fill tables, append to the session log,
> keep the status line current. If it disagrees with `soul.md` on a *fact*,
> flag it under "Questions for the maintainer" and trust your own verified
> evidence.

**Status:** Phase 0 — not started · Branch: `feature/v1-multiplatform` (not yet cloned) · Last session: —

## Human prerequisites (owner, before/at first session)

Things a human must do on the physical Mac — the agent cannot and must not:

- [ ] System Settings → Privacy & Security: grant **Microphone** and **Screen
      Recording** to the terminal app ZCode runs from (and re-check after any
      macOS upgrade — Screen Recording re-prompts).
- [ ] One manual mic sanity check (QuickTime voice memo) so silent-mic issues
      are never confused with porting bugs.
- [ ] Tailscale installed and running on this Mac (owner browses the UI
      remotely; also confirms the machine's tailnet IP for Phase 2).
- [ ] `sudo pmset -a sleep 0` (or lid kept open + plugged in + caffeinate) so
      tests don't die mid-run.

## Phase 0 — Recon & environment

- [ ] Xcode CLT installed (`xcode-select -p` succeeds)
- [ ] brew: `portaudio`, `ffmpeg`, `pyenv` installed (`blackhole-2ch` optional)
- [ ] pyenv Python **3.10.6** active (`python --version`)
- [ ] Fresh clone from https://github.com/igoor-noprofit/igoor, checked out `feature/v1-multiplatform`
- [ ] Campaign branch created: `git checkout -b feature/v1-for-macos-verification`
- [ ] `AGENTS.md` read in full — **Multiplatform Rules section included**
- [ ] `COMPAT_UBUNTU.md` read (the Linux census — your baseline for comparison); `MACOS_TEST.md` skimmed as historical background

**Pass when:** every box ticked.

## Phase 1 — Fresh-venv install test + first headless boot

The install test is deliberately FIRST: it is the arm64 wheel-gap detector.

- [ ] `python -m venv venv && source venv/bin/activate && pip install --upgrade pip`
- [ ] `pip install -r requirements.txt` succeeds on a **clean** venv (any resolution failure → record package/version, propose fix under Questions; this is exactly the beartype-class bug)
- [ ] `pip list | grep -iE "pywin32|pywinauto|comtypes|pythonnet|winrt|pywinusb|pyreadline"` prints nothing
- [ ] `python -c "from utils import get_appdata_dir; print(get_appdata_dir())"` prints `/Users/<you>/Library/Application Support/igoor`
- [ ] `IGOOR_HEADLESS=true python main.py` boots with no fatal traceback
- [ ] `curl http://127.0.0.1:9714/health` → `{"status":"ok"}`
- [ ] `http://127.0.0.1:9714/` serves the full IGOOR UI in a browser
- [ ] `~/Library/Application Support/igoor/` created with `settings.json`, `database/`, `plugins/`, `logs/`

**Evidence to capture:** install log tail, full startup log, UI screenshot, `ls` of the app-support dir.

## Phase 2 — Runtime modes + remote access on macOS

- [ ] Default boot (no flags): `lsof -iTCP:9714 -sTCP:LISTEN` shows `localhost:9714` only
- [ ] `IGOOR_HEADLESS=true IGOOR_ACCESS_FROM_OUTSIDE=true python main.py`: listener shows `*:9714`
- [ ] Owner (or you, via the tailnet IP) opens `http://<mac-tailnet-ip>:9714` from a remote browser → full UI works, same-origin URLs hold
- [ ] With external access on, trigger a TTS test (pockettts `test_speak` if configured, else any streaming-capable TTS) and confirm the log shows the browser-streaming path (`TTS stream ...: first chunk sent`); with a real browser connected, confirm playback + no error
- [ ] `is_remote_ui()` truth check in-process for the four flag combinations (pattern in COMPAT_UBUNTU §re-verification)

## Phase 3 — Plugin census (macOS)

- [ ] `curl -s http://127.0.0.1:9714/api/plugins/by-category` captured; startup + per-plugin logs reviewed
- [ ] Census table below fully filled; verdicts compared against COMPAT_UBUNTU's census (same plugin, different OS — differences are the interesting rows)
- [ ] `ttsdefault` + `extkeyb` verified: `compatible: false`, `active: false`, disabled card, never loaded (no import attempt in log)

Reminder: cloud plugins without API keys and audio paths without hardware/permission are **not** porting bugs — say which is which.

## Phase 4 — macOS-specific verifications

- [ ] **Native window**: plain `python main.py` (GUI mode) opens the pywebview/WKWebView window; capture a screenshot (`screencapture`) as evidence. If it fails, browser mode is the workaround — record the error verbatim.
- [ ] **Idle detection**: `_get_idle_time_macos()` returns sane values (log or small script); no crash in IdleDetector startup.
- [ ] **Screenshots**: bugreport plugin captures (or fails cleanly with the TCC reason).
- [ ] **ASR without live mic**: POST a wav to `/api/plugins/asrjs/transcribe` → 200 + sherpa-onnx inference in the log (arm64 inference verified). If live mic is available (permission granted), one real capture on top.
- [ ] **clock locale**: check the log for the locale fallback noise (known on Linux); record behavior.
- [ ] **Audio loopback (optional)**: with BlackHole installed, route TTS output back in and confirm end-to-end audio without human ears.

## Phase 5 — Report & hand-off

- [ ] `COMPAT_MACOS.md` written at repo root, modeled on `COMPAT_UBUNTU.md`: verified areas table, census, troubleshooting **actually encountered**, evidence appendix, "no Windows regression" argument
- [ ] `MACOS_TEST.md` marked superseded (one-line pointer to COMPAT_MACOS.md)
- [ ] Any code changes: surgical, platform-gated, `py_compile` clean, headless boot re-verified, conventional commits on the campaign branch; nothing pushed without the owner's go-ahead (fallback: `git bundle` + note)
- [ ] Session log complete; "Questions for the maintainer" up to date

**Definition of done:** every box ticked, `COMPAT_MACOS.md` complete with evidence, and the maintainer can review the macOS story in one sitting.

## Plugin census (fill during Phase 3)

Verdict legend: **works** / **fails** (cause known) / **portable-now** / **portable-with-effort** / **windows-only**.

| Plugin | Loads? | Root cause if not | Verdict | Evidence |
|---|---|---|---|---|
| asrjs | | | | |
| autocomplete | | | | |
| biorecorder | | | | |
| bugreport | | | | |
| clock | | | | |
| conversation | | | | |
| daily | | | | |
| elevenlabstts | | | | |
| extkeyb | | | windows-only (expected) | |
| flow | | | | |
| localtts | | | | |
| memory | | | | |
| meteo | | | | |
| onboarding | | | | |
| pockettts | | | | |
| rag | | | | |
| ramcpu | | | | |
| recorder | | | | |
| shortcuts | | | | |
| speakerid | | | | |
| speechifytts | | | | |
| survey | | | | |
| translator | | | | |
| ttsdefault | | | windows-only (expected) | |

## Questions for the maintainer

Append with date and context; never block on these.

- _(none yet)_

## Session log (newest on top)

```
### YYYY-MM-DD HH:MM — <session goal>
Done: ...
Found: ...
Decided: ...
Next: ...
```
