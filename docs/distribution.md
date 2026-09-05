# IGOOR Windows distribution strategy

## Decision record (2026-09)

Goal: eliminate the SmartScreen "Windows protected your PC" interstitial for
users (people with neurodegenerative diseases / paralysis — extra clicks are
real barriers) and make installs and updates as easy as possible.

| Option | Verdict | Why |
|---|---|---|
| SignPath Foundation (free OSS signing) | Applied, **rejected** | — |
| Certum OV code signing (card €69 or Cloud €49/yr) | **Shelved** | OV reputation needs "several weeks and hundreds of clean installs" (Microsoft); at IGOOR's niche-app volume the ramp may never complete. EV no longer grants instant reputation either (2024+). |
| Azure Artifact Signing | **Not available** | Requires a registered organization in US/CA/EU/UK with 3+ years of history; IGOOR has no registered legal entity. |
| **Microsoft Store (MSIX)** | **Chosen** | Store-signed = no SmartScreen at all, free hosting, auto-updates, per-user install without admin/UAC. Free individual developer account. |

Fallback: if MSIX proves impossible, revive the Certum Cloud plan
(shop.certum.eu "Open Source Code Signing in the Cloud", SimplySign, €49/yr,
signtool + http://timestamp.certum.pl).

Direct downloads via GitHub Releases (Inno Setup `IGOOR.exe`) continue
unchanged for locked-down / IT-managed machines.

## MSIX spike results (2026-09-04, FINAL: PASS)

**Verdict: PASS. IGOOR launches inside the MSIX container on a normal
Windows PC (window opens with the IGOOR logo). The dev machine's activation
failure is a local anomaly of that machine, not a blocker.**

What is proven:
- **The app runs in the container**: on a second Windows PC the package
  installs and launches with its window. The interactive test matrix below
  can now be run there.
- Packaging works: `installer/msix/build_msix.bat` produces a valid, signed
  MSIX (11,118 files / ~1.2 GB incl. a full torch stack), installs with
  `Status: Ok`. Production `.env` handled via `env.production` (the repo
  `.env` carries dev flags — see Gotcha #2).
- The app binary is fine: the same build runs normally from `dist\`.

Expected sideload behavior on test machines: launching shows
`0x800B010A` (CERT_E_UNTRUSTEDROOT) — the self-signed test cert is not
trusted there. Fix on each test machine (elevated PowerShell):

    Import-Certificate -FilePath IGOORMsixTest.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
    Import-Certificate -FilePath IGOORMsixTest.cer -CertStoreLocation Cert:\LocalMachine\Root

**Store users never see this**: Partner Center re-signs submissions with a
Microsoft certificate that chains to a root trusted on every Windows PC.

Dev-machine anomaly (for the record): that Windows 11 25H2 machine (build
26200) refuses to *activate* any self-signed MSIX — Start-menu activation
fails (TWinUI 5961, `0x8027025B`, phase `COM ActivateExtension`, no process
created), and direct/alias launches die in the PyInstaller bootloader with
exit code 91 (`LoadLibrary(_internal\python310.dll)` → WinError 5 —
WindowsApps grants code execution only to processes with package identity,
which no launch path granted there). Also reproduced with a winver.exe probe
package, so not IGOOR-specific. Store-signed apps activate fine on it.
Build/test MSIX work on other machines.

### Gotcha #2 — the bundled .env carries dev flags

The PyInstaller bundle includes the repo `.env`, which on the dev machine
contains `IGOOR_HEADLESS=True`, `IGOOR_ACCESS_FROM_OUTSIDE=True`,
`IGOOR_DEBUG=True`. MSIX cannot rewrite .env at install time (Inno Setup
did), so `build_msix.bat` overwrites `layout\_internal\.env` with
`installer/msix/env.production`. Longer term (Stage 2): first-run
language/config init instead of any bundled .env.

### Interactive test matrix (once the app launches locally)

- [ ] Package installs; launches from Start menu
- [ ] Main window renders (WebView2 UI)
- [ ] Eye-tracking input works (selection/clicking through the UI)
- [ ] TTS speaks (audio out) and ASR/mic capture works (audio in)
- [ ] Conversation with the LLM works (keys from APPDATA settings)
- [ ] HuggingFace model downloads land in APPDATA
- [ ] Plugins activate/deactivate; no writes inside `C:\Program Files\WindowsApps`
- [ ] Language/settings behave on first run
- [ ] Uninstall from Settings removes the app cleanly

### Corrections log (diary of wrong turns, kept to avoid repeats)

- "Container boot PROVEN at 07:23" was WRONG — that process was a leftover
  dev instance; the packaged app has never logged a single line.
- "Direct run exits 1" was a failed `cd` (bash), not the app.
- `get_version.ps1` writes to stderr; redirect with `>` captures nothing
  (fixed in `build_msix.bat` by parsing `version.py` directly).
- `makeappx pack` HANGS when run through a background-task pipe wrapper
  (output pipe never drains, 0% CPU forever); it completes reliably in a
  foreground shell. Run builds in the foreground.

## Store submission state (2026-09-04)

Manifest now carries the real Partner Center identity:
`Name="IGOOR.IGOOR"`, `Publisher="CN=AFF811DC-40E0-4A1D-A8C8-AA38A5208E53"`.
`IGOOR-1.1.0.0.msix` is signed with a self-signed cert whose subject equals
that Publisher (thumbprint `029A3BD0…E999`, see `make_test_cert.ps1`) — the
sideload trust step on test machines applies to THIS cert now; the earlier
"CN=IGOOR MSIX Test" cert is obsolete. The same .msix is uploadable to
Partner Center (Store re-signs — no cert trust needed for Store users).
Still needed before submission: listing (description, privacy-policy URL —
LLM API calls, age rating, accessibility category), and ideally a private
package flight to verify the Store-signed install experience.

## Open issue (not MSIX-related)

2026-09-04: `dist\igoor` was found emptied (11k files gone, folder timestamp
unchanged, no build started). Cause unknown — no project script or agent
command explains it. Rebuilt via `create_exe.bat`. If it recurs, suspect
antivirus cleanup or an interrupted external tool.

## Update 2026-09-05: THE root cause found; mic capability added

**The activation bug that blocked everything was a single manifest value:**
`EntryPoint` must be **`Windows.FullTrustApplication`**, NOT
`Windows.FullTrustProcess`. The wrong value passes makeappx, passes
installation, passes Store certification - and then activation fails
silently (TWinUI 5961, 0x8027025B, phase "COM ActivateExtension", no
process ever created) on every machine. Found by dumping Windows
Terminal's manifest for comparison - always diff against a known-good
reference. With the fix, the packaged app launches end-to-end (window,
plugins, logging to real %APPDATA% - which also confirms uninstall
preserves user data).

**Microphone**: packaged apps are gated by Windows per-app privacy
settings; without a capability declaration the toggle defaults off and
asrjs fails with "Permission denied by system" in the pywebview window
(browser access works because the browser owns its own mic grant).
Fixed by declaring `<DeviceCapability Name="microphone" />` in the
manifest (NOT `<uap:Capability>` - that fails schema validation). Users
now get the normal one-time consent dialog.

Both fixes are in AppxManifest.xml; version bumped to 1.1.1 for the
Store resubmission (higher version than the published 1.1.0.0 is
mandatory). Submission: private audience -> Surface test -> public.
