"""System tray icon for IGOOR headless mode.

Gives the headless server (IGOOR_HEADLESS=true) a visible presence in the
notification area: a status tooltip fed by StatusManager, an "Open interface"
shortcut and a clean Quit. Everything degrades gracefully: if pystray or a
notification area is unavailable (minimal install, SSH session without a
desktop), headless keeps running without it — same contract as the tkinter
splash screen in GUI mode.
"""

import logging
import webbrowser

from utils import get_appdata_dir, resource_path, setup_logger

logger = setup_logger('tray', get_appdata_dir())

TRAY_URL = "http://127.0.0.1:9714/"


def start_tray_icon(shutdown_event):
    """Create the tray icon and return it, or None if unavailable.

    shutdown_event is passed in (rather than imported from main) so this
    module never imports main, which would re-execute it as __main__.
    """
    # Lazy import: pystray must stay optional (module importable everywhere).
    try:
        import pystray
        from PIL import Image
    except ImportError:
        logger.warning("pystray not available - tray icon disabled")
        return None

    try:
        icon_image = Image.open(resource_path('img/logo_ig_lxL_icon.ico')).convert('RGBA')
        if icon_image.size[0] > 64:
            icon_image = icon_image.resize((64, 64), Image.LANCZOS)

        def on_open_interface(icon, item):
            webbrowser.open(TRAY_URL)

        def on_quit(icon, item):
            shutdown_event.set()

        icon = pystray.Icon(
            'IGOOR',
            icon_image,
            title="IGOOR — starting…",
            menu=pystray.Menu(
                pystray.MenuItem('Open interface', on_open_interface, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', on_quit),
            ),
        )
        icon.run_detached()
    except Exception as e:
        logger.warning(f"Tray icon unavailable ({e}) - continuing without it")
        return None

    class TrayStatusObserver:
        """Mirrors StatusManager into the tray tooltip, like TkSplashObserver."""

        def update_status(self, status: str):
            try:
                icon.title = f"IGOOR — {str(status)[:120]}"
            except Exception:
                pass

    try:
        from status_manager import StatusManager
        StatusManager().register_observer(TrayStatusObserver())
        icon.title = f"IGOOR — {StatusManager().get_status()}"
        icon.notify(f"IGOOR running on {TRAY_URL}", "IGOOR")
    except Exception as e:
        logger.warning(f"Tray status wiring failed: {e}")

    logger.info("Tray icon started")
    return icon


def stop_tray_icon(icon):
    """Remove the tray icon (safe to call with None)."""
    if icon is None:
        return
    try:
        icon.stop()
    except Exception as e:
        logger.warning(f"Failed stopping tray icon: {e}")
