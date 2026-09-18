"""Automatic HTTPS exposure via `tailscale serve` for IGOOR server mode.

When IGOOR accepts external access (IGOOR_ACCESS_FROM_OUTSIDE=true) and the
Tailscale CLI is installed, IGOOR enables `tailscale serve --bg
localhost:9714` so remote browsers get the UI over HTTPS
(https://<machine>.<tailnet>.ts.net). Browsers only offer microphone access
on secure origins, so this completes the tablet/remote setup without any
manual command line.

The serve config lives inside Tailscale and persists across reboots, so
only the first run does work: on Windows it asks one UAC elevation
(`tailscale serve` talks to tailscaled through an admin-only pipe), later
startups just detect that port 9714 is already served. If Tailscale is
absent, not running, or already serving something else, nothing is touched.

Everything degrades gracefully: any failure is logged as a warning and
IGOOR keeps running — same contract as tray_icon.py.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time

from utils import get_appdata_dir, get_platform_key, setup_logger

logger = setup_logger('tailscale', get_appdata_dir())

PORT = 9714
TSNET_URL_RE = re.compile(r'https://[A-Za-z0-9.-]+')


def find_tailscale():
    """Locate the tailscale CLI, or None when Tailscale is not installed."""
    found = shutil.which('tailscale')
    if found:
        return found
    key = get_platform_key()
    if key == 'windows':
        candidates = [
            os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Tailscale', 'tailscale.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Tailscale', 'tailscale.exe'),
        ]
    elif key == 'macos':
        candidates = [
            '/Applications/Tailscale.app/Contents/MacOS/Tailscale',
            '/usr/local/bin/tailscale',
        ]
    else:
        candidates = ['/usr/bin/tailscale', '/usr/local/bin/tailscale']
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _run_ts(ts, args, timeout):
    cmd = [ts] + list(args)
    kwargs = {}
    if get_platform_key() == 'windows':
        # The packaged exe has no console: don't flash one for the CLI.
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kwargs)


def _serve_state(ts):
    """Inspect the current tailscale serve config.

    Returns (state, url): state is 'served' when our port is already
    proxied (url may be None if the address could not be parsed), 'conflict'
    when port 443 serves a different target, 'idle' when nothing is served,
    'unknown' when the status could not be read.
    """
    r = _run_ts(ts, ['serve', 'status'], timeout=10)
    out = (r.stdout or '') + (r.stderr or '')
    if r.returncode != 0:
        return 'unknown', None
    if str(PORT) in out:
        # This node's current DNS name is the only hostname with a valid
        # certificate: serve status text may still list entries under an
        # old machine name (rename leftovers) that fail TLS.
        url = _self_dns_url(ts) or _url_from_text(out)
        _warn_stale_names(out, url)
        return 'served', url
    if 'http' in out:
        return 'conflict', None
    return 'idle', None


def _url_from_text(out):
    m = TSNET_URL_RE.search(out)
    return m.group(0) if m else None


def _warn_stale_names(out, current_url):
    """Heads-up about serve entries under another hostname: they proxy but
    have no matching certificate, so clients get TLS errors on them."""
    if not current_url:
        return
    current_host = current_url.split('//', 1)[-1]
    for found in TSNET_URL_RE.findall(out):
        if found.split('//', 1)[-1] != current_host:
            logger.warning(
                f"Stale tailscale serve entry for {found} (no certificate for it - old machine name?): "
                "clients using it get TLS errors. Clean it up with `tailscale serve status` / `tailscale serve reset`.")
            return
    if 'http' in out:
        return 'conflict', None
    return 'idle', None


def _self_dns_url(ts):
    """Best-effort https URL of this machine from `tailscale status --json`."""
    try:
        r = _run_ts(ts, ['status', '--json'], timeout=10)
        dns = json.loads(r.stdout).get('Self', {}).get('DNSName', '').rstrip('.')
        return f'https://{dns}' if dns else None
    except Exception:
        return None


def _serve_elevated_windows(ts):
    """Run `tailscale serve --bg` elevated (the tailscaled pipe is
    admin-only on Windows): asks one UAC prompt, False if refused/closed."""
    import ctypes
    SW_HIDE = 0
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', ts, f'serve --bg --yes localhost:{PORT}', None, SW_HIDE)
    return ret > 32


def _friendly_error(r):
    lines = (r.stderr or r.stdout or '').strip().splitlines()
    detail = lines[0] if lines else f'exit code {r.returncode}'
    low = detail.lower()
    if 'https' in low or 'cert' in low or 'dns' in low:
        detail += ' - enable HTTPS certificates in the Tailscale admin console (https://login.tailscale.com/admin/dns)'
    return detail


def _wait_for_serve(ts, attempts=10):
    for _ in range(attempts):
        state, url = _serve_state(ts)
        if state == 'served':
            return url
        if state == 'conflict':
            return None
        time.sleep(1)
    return None


def _notify(icon, text):
    """Best-effort tray notification (icon is None in GUI mode)."""
    if icon is None:
        return
    try:
        icon.notify(text, 'IGOOR')
    except Exception:
        pass


def enable_tailscale_serve(force=False, icon=None):
    """Expose the UI over HTTPS via `tailscale serve`. Never raises.

    Runs automatically at startup (force=False, gated on
    IGOOR_ACCESS_FROM_OUTSIDE=true) and from the tray menu (force=True).
    Returns (ok, url): url is the https address when it could be determined.
    """
    try:
        return _enable_tailscale_serve(force, icon)
    except Exception as e:
        logger.warning(f"Tailscale HTTPS setup failed: {e}")
        _notify(icon, 'Could not enable Tailscale HTTPS - see logs')
        return False, None


def _enable_tailscale_serve(force, icon):
    outside = os.getenv('IGOOR_ACCESS_FROM_OUTSIDE', 'False').lower() == 'true'
    if not (outside or force):
        logger.info("IGOOR_ACCESS_FROM_OUTSIDE is not enabled - no HTTPS setup needed")
        return False, None

    ts = find_tailscale()
    if not ts:
        logger.info("Tailscale not installed - HTTPS setup skipped")
        return False, None

    status = _run_ts(ts, ['status'], timeout=5)
    if status.returncode != 0:
        logger.warning("Tailscale is installed but not running/logged in - HTTPS setup skipped")
        return False, None

    state, url = _serve_state(ts)
    if state == 'served':
        logger.info(f"tailscale serve already active: {url or f'port {PORT}'}")
        _notify(icon, f"Secure access active: {url}" if url else f"Secure access active on port {PORT}")
        return True, url
    if state == 'conflict':
        logger.warning("tailscale serve already proxies another target - leaving it untouched (see `tailscale serve status`)")
        return False, None
    if state == 'unknown':
        logger.warning("Could not read the tailscale serve status - HTTPS setup skipped")
        return False, None

    logger.info(f"Enabling tailscale serve for localhost:{PORT}...")
    if get_platform_key() == 'windows':
        if not _serve_elevated_windows(ts):
            logger.warning("Tailscale HTTPS setup was not authorized (UAC refused or closed) - retry it from the tray icon menu")
            return False, None
    else:
        r = _run_ts(ts, ['serve', '--bg', '--yes', f'localhost:{PORT}'], timeout=30)
        if r.returncode != 0:
            logger.warning(f"tailscale serve failed: {_friendly_error(r)}")
            return False, None

    url = _wait_for_serve(ts)
    if url is None:
        logger.warning("tailscale serve did not become active - check `tailscale serve status`")
        return False, None
    logger.info(f"Secure access enabled: {url}")
    _notify(icon, f"Secure access enabled: {url}")
    return True, url


def auto_enable_tailscale_serve(icon=None):
    """Startup helper: fire-and-forget the setup on its own daemon thread,
    so a pending UAC prompt never blocks startup."""
    thread = threading.Thread(
        target=enable_tailscale_serve, kwargs={'icon': icon},
        daemon=True, name='tailscale-serve')
    thread.start()
    return thread
