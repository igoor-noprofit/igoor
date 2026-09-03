# Running IGOOR as an always-on headless server

These recipes keep IGOOR running in headless server mode (`IGOOR_HEADLESS=true`,
`IGOOR_ACCESS_FROM_OUTSIDE=true` in the repo `.env`) and restart it automatically
after a crash **and** after a machine reboot. The UI is then any browser that can
reach the machine (e.g. its Tailscale IP, on a trusted network — external access
is unauthenticated).

## Windows

1. Check the repo `.env`: `IGOOR_HEADLESS=False` → `True`, `IGOOR_ACCESS_FROM_OUTSIDE=False` → `True`.
2. Test the watchdog once: double-click `windows\igoor_server_watchdog.bat`
   (or run it in a terminal). It starts IGOOR and restarts it ~5 s after any exit.
   Stop testing by closing the window / pressing Ctrl+C twice.
3. Make it permanent: double-click `windows\install_server_startup.bat`. This puts a
   shortcut in your **Startup folder** that launches the watchdog **hidden** at every
   logon — no administrator rights needed. It can also start it immediately.
4. Remove it again with `windows\uninstall_server_startup.bat`.

Notes:

- The Startup folder belongs to **your user**, so `%APPDATA%\igoor` keeps pointing
  at your real profile (a system service running as SYSTEM would silently move all
  IGOOR data to the system profile — avoid that).
- "At logon" means the machine must log into Windows. For a dedicated IGOOR box,
  enable Windows auto-login (netplwiz → user without password prompt).
- **Advanced:** Task Scheduler (`schtasks /Create /SC ONLOGON ...`) offers richer
  scheduling but creating logon-trigger tasks requires an administrator prompt;
  a true Windows service via [NSSM](https://nssm.cc/) or WinSW starts at boot with
  no logged-in user. If you use NSSM manually, install the service to run as your
  user account, not LocalSystem, for the same APPDATA reason. These are candidate
  mechanisms for a future installer.

## Linux

```bash
mkdir -p ~/.config/systemd/user
cp linux/igoor.service ~/.config/systemd/user/
# edit the file: adjust WorkingDirectory and ExecStart to your clone
systemctl --user daemon-reload
systemctl --user enable --now igoor
loginctl enable-linger "$USER"        # keep running after logout
journalctl --user -u igoor -f         # follow logs
```

A user unit (not a system unit) keeps `~/.igoor` owned by your user.

## macOS

```bash
# edit macos/org.igoor.server.plist first: replace CHANGE_ME with your username/clone path
cp macos/org.igoor.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/org.igoor.server.plist
# stop: launchctl unload ~/Library/LaunchAgents/org.igoor.server.plist
```

## What you get

- The server machine survives IGOOR crashes (restart within ~5 s) and reboots
  (auto-started again).
- Remote browsers that were connected during a restart will show the
  "Connection lost — reconnecting…" overlay and **reload themselves** as soon
  as the server is back, so all plugin websockets and state are re-established
  cleanly (this is why a bare restart needs no manual page refresh).
