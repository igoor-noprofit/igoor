from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from utils import (
    get_appdata_dir,
    get_appdata_web_dir,
    get_appdata_web_js_dir,
    resource_path,
    setup_logger,
)
from websocket_server import websocket_server


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

    # Static mounts for packaged assets
    app.mount("/css", StaticFiles(directory=resource_path("css")), name="css")
    app.mount("/img", StaticFiles(directory=resource_path("img")), name="img")
    app.mount("/plugins", StaticFiles(directory=resource_path("plugins")), name="plugins")
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
