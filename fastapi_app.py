from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
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
        settings_manager.update_plugin_settings(plugin_name, payload.settings)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @api_router.post("/plugins/{plugin_name}/toggle")
    async def api_toggle_plugin(plugin_name: str, payload: TogglePluginPayload):
        try:
            if payload.active:
                plugin_manager.activate_plugin(plugin_name)
            else:
                plugin_manager.deactivate_plugin(plugin_name)
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

    @api_router.get("/context")
    async def api_get_context():
        return context_manager.get_context()

    app.include_router(api_router)

    # Static mounts for packaged assets
    app.mount("/css", StaticFiles(directory=resource_path("css")), name="css")
    app.mount("/img", StaticFiles(directory=resource_path("img")), name="img")
    app.mount("/plugins", StaticFiles(directory=resource_path("plugins")), name="plugins")
    app.mount("/locales", StaticFiles(directory=resource_path("locales")), name="locales")
    @app.websocket("/ws/{plugin_name}")
    async def websocket_endpoint(websocket: WebSocket, plugin_name: str):
        name = plugin_name.strip("/") or "app"
        await websocket_server.connect(name, websocket)
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
        path = Path(resource_path("index.html"))
        logger.debug(f"Serving index.html from {path}")
        return _file_response(path, media_type="text/html; charset=utf-8")

    @app.get("/")
    async def root():
        path = Path(resource_path("index.html"))
        logger.debug("Serving root index")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/health")
    async def healthcheck():
        return JSONResponse({"status": "ok"})

    return app


app = create_app()
