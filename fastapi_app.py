from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from utils import (
    get_appdata_dir,
    get_appdata_web_dir,
    get_appdata_web_js_dir,
    resource_path,
    setup_logger,
)
from websocket_server import websocket_server
from plugin_manager import PluginManager
from settings_manager import SettingsManager
from context_manager import context_manager
from data_manager import DataManager
from version import __version__ as IGOOR_VERSION


class UpdateSettingsPayload(BaseModel):
    settings: dict


class ChangeViewPayload(BaseModel):
    lastview: Optional[str] = None
    view: str


class TogglePluginPayload(BaseModel):
    active: bool

def _ensure_web_directories() -> None:
    """Ensure writable web directories exist in APPDATA."""
    get_appdata_dir(create=True)
    get_appdata_web_dir(create=True)
    get_appdata_web_js_dir(create=True)


def _file_response(path: Path, media_type: Optional[str] = None):
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    return FileResponse(path, media_type=media_type)


def _serve_index_html() -> HTMLResponse:
    """Serve index.html with the current app version injected for cache-busting.

    {{VERSION}} tokens in asset URLs are replaced with the IGOOR version, and
    the document is sent with Cache-Control: no-store so Edge WebView2 always
    re-fetches it — guaranteeing the latest ?v= tags reach the client after an
    upgrade.
    """
    path = Path(resource_path("index.html"))
    content = path.read_text(encoding="utf-8").replace("{{VERSION}}", IGOOR_VERSION)
    return HTMLResponse(content, headers={"Cache-Control": "no-store"})


def _load_whatsnew_entries(lang: Optional[str]) -> list:
    """Read locales/<lang>/whatsnew.json highlights for the current version.
    A locale that has no entry for the version falls back to en_EN (same
    convention as plugin translations); empty result means no dialog."""
    for candidate in (lang, "en_EN"):
        if not candidate:
            continue
        path = Path(resource_path(os.path.join("locales", candidate, "whatsnew.json")))
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get(IGOOR_VERSION, [])
            if isinstance(entries, list) and entries:
                return entries
        except (OSError, json.JSONDecodeError):
            continue
    return []


def create_app() -> FastAPI:
    """Create FastAPI application with static asset mounting."""

    _ensure_web_directories()

    appdata_dir = Path(get_appdata_dir(create=True))
    logger = setup_logger("fastapi", str(appdata_dir))

    app = FastAPI(title="IGOOR API", docs_url=None, redoc_url=None)

    api_router = APIRouter(prefix="/api", tags=["api"])

    plugin_manager = PluginManager()
    plugin_manager.fastapi_app = app
    settings_manager = SettingsManager()

    @api_router.get("/plugins/by-category")
    async def api_get_plugins_by_category():
        return plugin_manager.get_plugins_by_category()

    @api_router.get("/plugins/{plugin_name}/settings")
    async def api_get_plugin_settings(plugin_name: str):
        return plugin_manager.plugin_has_settings(plugin_name, return_settings=True) or {}

    @api_router.post(
        "/plugins/{plugin_name}/settings",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def api_update_plugin_settings(
        plugin_name: str, payload: UpdateSettingsPayload
    ):
        if plugin_name == "asrjs":
            # A manual save in the asrjs settings reclaims engine control from
            # the onboarding provider matrix ("unless otherwise stated later").
            payload.settings["asr_managed_by_onboarding"] = False
        settings_manager.update_plugin_settings(plugin_name, payload.settings, plugin_manager)
        # settings_updated is triggered inside update_plugin_settings (it
        # receives plugin_manager); triggering it here too fired the hook twice.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @api_router.post("/settings/reload")
    async def api_reload_settings():
        """Force reload settings from disk and notify all plugins."""
        settings_manager.load_and_notify(plugin_manager)
        return {"status": "ok"}

    @api_router.post("/app/restart")
    async def api_restart_app():
        """Restart the application: needed after a data import, because plugin
        (de)activations only take effect at boot. Spawns a detached copy of the
        current process, then exits."""
        def _restart():
            try:
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                # DETACHED_PROCESS leaves the child without a console: with
                # invalid stdio the child's uvicorn logging/startup dies
                # silently and the new window loads an error page. Give it
                # real file handles (its diagnostics land there) and an
                # absolute script path so it does not depend on our cwd.
                script = sys.argv[0] if os.path.isabs(sys.argv[0]) else os.path.abspath(sys.argv[0])
                log_path = os.path.join(get_appdata_dir(), "logs", "restart_child.log")
                log_file = open(log_path, "ab")
                subprocess.Popen(
                    [sys.executable, script] + sys.argv[1:],
                    creationflags=flags,
                    stdout=log_file,
                    stderr=log_file,
                    stdin=subprocess.DEVNULL,
                    cwd=os.path.dirname(script) or None,
                )
                logger.info(f"Restart child spawned; output -> {log_path}")
            except Exception as exc:
                logger.error(f"Could not spawn restart process: {exc}")
            finally:
                os._exit(0)

        logger.info("Restart requested via REST - restarting the application")
        threading.Timer(0.5, _restart).start()
        return {"status": "ok"}

    @api_router.post("/app/quit")
    async def api_quit_app():
        """Close the application without relaunching it. The onboarding wizard
        uses this after a language change: the user is told to relaunch IGOOR,
        which avoids the restart port race (the old process releases the port
        only during teardown, so an immediately spawned child can fail to
        bind) and needs no detached-process tricks."""
        logger.info("Quit requested via REST - closing the application")
        threading.Timer(0.5, os._exit, args=(0,)).start()
        return {"status": "ok"}

    @api_router.post("/plugins/{plugin_name}/toggle")
    async def api_toggle_plugin(plugin_name: str, payload: TogglePluginPayload):
        try:
            if payload.active:
                if not plugin_manager.activate_plugin(plugin_name):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Plugin '{plugin_name}' is not available on this platform",
                    )
            else:
                plugin_manager.deactivate_plugin(plugin_name)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"status": "ok"}

    @api_router.post("/hooks/{hook_name}")
    async def api_trigger_hook(hook_name: str, payload: Dict[str, object]):
        kwargs = payload or {}
        try:
            result = await plugin_manager.trigger_hook(hook_name, **kwargs)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"result": result}

    @api_router.post("/app/change-view", status_code=status.HTTP_204_NO_CONTENT)
    async def api_change_view(payload: ChangeViewPayload):
        try:
            await plugin_manager.trigger_hook(
                "change_view",
                lastview=payload.lastview,
                currentview=payload.view,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @api_router.get("/app/whatsnew")
    async def api_get_whatsnew():
        """Tell the frontend whether this boot follows an app update, plus the
        locale'd highlights for the current version. `whatsnew_last_shown` is
        only advanced by the dismiss endpoint, so the dialog shows once."""
        s = settings_manager.get_settings()
        shown_for = s.get("whatsnew_last_shown")
        upgraded = bool(shown_for) and shown_for != IGOOR_VERSION
        entries = _load_whatsnew_entries(settings_manager.get_lang()) if upgraded else []
        return {"upgraded": upgraded, "version": IGOOR_VERSION, "entries": entries}

    @api_router.post("/app/whatsnew/dismiss")
    async def api_dismiss_whatsnew():
        s = settings_manager.get_settings()
        s["whatsnew_last_shown"] = IGOOR_VERSION
        settings_manager.save_settings()
        return {"status": "ok"}

    @api_router.get("/app/clipboard")
    async def api_get_clipboard():
        """Return the OS clipboard text so the UI can offer a Paste button.

        WKWebView (pywebview on macOS) does not route the Cmd+V shortcut to web
        inputs, and the async Clipboard API is unavailable there — the desktop
        frontend reads the clipboard through this endpoint instead.
        """
        import platform as _platform
        import subprocess

        system = _platform.system()
        text = ""
        try:
            if system == "Darwin":
                text = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2).stdout
            elif system == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                    capture_output=True, text=True, timeout=3,
                )
                text = result.stdout.rstrip("\r\n")
            else:
                for cmd in (["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]):
                    try:
                        text = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
                        break
                    except FileNotFoundError:
                        continue
        except Exception as exc:
            logger.warning(f"Could not read clipboard: {exc}")
        return {"text": text}

    @api_router.get("/context")
    async def api_get_context():
        return context_manager.get_context()

    @api_router.get("/data/export")
    async def api_export_data(include_rag: bool = Query(True)):
        """Export user data (settings, database, RAG plugin data) to a ZIP file."""
        try:
            data_manager = DataManager()
            result = data_manager.export_user_data(include_rag=include_rag)
            
            if not result.get("success"):
                raise HTTPException(status_code=500, detail=result.get("message"))
            
            zip_path = result.get("file_path")
            return FileResponse(
                zip_path,
                media_type="application/zip",
                filename=os.path.basename(zip_path)
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @api_router.post("/data/import")
    async def api_import_data(file: UploadFile, overwrite_settings: bool = False):
        """Import user data from a ZIP file."""
        try:
            data_manager = DataManager()
            
            # Save uploaded file to temp location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                result = data_manager.import_user_data(temp_file_path, overwrite_settings=overwrite_settings)
                
                if not result.get("success"):
                    raise HTTPException(status_code=500, detail=result.get("message"))
                
                # Reload settings to notify all plugins
                settings_manager.load_and_notify(plugin_manager)
                
                return {
                    "success": True,
                    "message": result.get("message"),
                    "warnings": result.get("warnings", []),
                    "version_info": result.get("version_info"),
                    "activation_changes": result.get("activation_changes", {}),
                    "summary": result.get("summary", {})
                }
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    app.include_router(api_router)

    # Static mounts for packaged assets
    app.mount("/css", StaticFiles(directory=resource_path("css")), name="css")
    app.mount("/img", StaticFiles(directory=resource_path("img")), name="img")
    app.mount("/plugins", StaticFiles(directory=resource_path("plugins")), name="plugins")
    app.mount("/locales", StaticFiles(directory=resource_path("locales")), name="locales")

    @app.middleware("http")
    async def revalidate_static_assets(request: Request, call_next):
        # Frontend assets (.vue/.js/.css served from the app root) change on every
        # upgrade; without an explicit Cache-Control the browser heuristic-caches
        # them and renders a stale UI until the cache happens to expire.
        response = await call_next(request)
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.websocket("/ws/{plugin_name}")
    async def websocket_endpoint(websocket: WebSocket, plugin_name: str):
        name = plugin_name.strip("/") or "app"
        await websocket_server.connect(name, websocket)
        if name == "app":
            # A (re)connecting app frontend needs the current view: on page
            # reload nothing else re-sends it (gui_ready fires once per boot),
            # which used to leave a refreshed browser stuck on the splash.
            try:
                await plugin_manager.trigger_hook("gui_ready")
            except Exception as exc:
                logger.warning(f"gui_ready re-fire on app connect failed: {exc}")
        try:
            while True:
                message = await websocket.receive_text()
                await websocket_server.handle_message(name, message)
        except WebSocketDisconnect:
            await websocket_server.disconnect(name, websocket)
        except Exception as exc:
            await websocket_server.disconnect(name, websocket)
            raise exc


    @app.get("/js/{asset_path:path}")
    async def get_js_resource(asset_path: str):
        dynamic_candidates = {
            "app.js": "application/javascript",
            "app.vue": "text/plain; charset=utf-8",
        }

        if asset_path in dynamic_candidates:
            path = Path(get_appdata_web_js_dir(create=True)) / asset_path
            media_type = dynamic_candidates[asset_path]
            logger.debug(f"Serving dynamic JS resource {asset_path} from {path}")
            return _file_response(path, media_type=media_type)

        packaged_path = Path(resource_path(os.path.join("js", asset_path)))
        if packaged_path.suffix == ".js":
            media_type = "application/javascript"
        elif packaged_path.suffix == ".vue":
            media_type = "text/plain; charset=utf-8"
        else:
            media_type = None

        logger.debug(f"Serving packaged JS resource {asset_path} from {packaged_path}")
        return _file_response(packaged_path, media_type=media_type)

    @app.get("/index.html")
    async def get_index_html():
        logger.debug("Serving index.html with version cache-busting")
        return _serve_index_html()

    @app.get("/")
    async def root():
        logger.debug("Serving root index with version cache-busting")
        return _serve_index_html()

    @app.get("/health")
    async def healthcheck():
        return JSONResponse({"status": "ok"})

    return app


app = create_app()
