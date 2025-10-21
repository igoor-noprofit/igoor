from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin


class Speakerid(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.router: Optional[APIRouter] = None

    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        self._ensure_router()
        fastapi_app = getattr(self.pm, "fastapi_app", None)
        if fastapi_app and not getattr(self, "_router_registered", False):
            fastapi_app.include_router(self.router)
            self._router_registered = True
        elif fastapi_app is None:
            self.logger.warning("FastAPI app not available; speakerid endpoints not registered")
        self.is_loaded = True

    def _ensure_router(self):
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/speakerid", tags=["speakerid"])

        @self.router.get("/speakers")
        async def list_speakers():
            rows = self.db_execute_sync("SELECT id, people_id FROM speakers ORDER BY id ASC") or []
            return rows

        @self.router.post("/speakers")
        async def add_speaker(payload: Dict[str, Any]):
            people_id = int(payload.get("people_id", 0))
            self.db_execute_sync("INSERT INTO speakers (people_id) VALUES (?)", (people_id,))
            row = self.db_execute_sync("SELECT id, people_id FROM speakers ORDER BY id DESC LIMIT 1")
            return row[0] if row else {"id": None, "people_id": people_id}

        @self.router.post("/records")
        async def attach_record(payload: Dict[str, Any]):
            recorder_id = payload.get("recorder_id")
            speakers_id = payload.get("speakers_id")
            if recorder_id is None or speakers_id is None:
                raise HTTPException(status_code=400, detail="recorder_id and speakers_id are required")
            self.db_execute_sync(
                "INSERT INTO records (recorder_id, speakers_id) VALUES (?, ?)",
                (recorder_id, speakers_id),
            )
            row = self.db_execute_sync(
                "SELECT id, recorder_id, speakers_id FROM records ORDER BY id DESC LIMIT 1"
            )
            return row[0] if row else {"id": None, "recorder_id": recorder_id, "speakers_id": speakers_id}


        @self.router.get("/records")
        async def list_records():
            rows = self.db_execute_sync(
                "SELECT id, recorder_id, speakers_id FROM records ORDER BY id DESC"
            ) or []
            return rows

    def db_execute_sync(self, query: str, params: tuple = ()):
        try:
            return super().db_execute_sync(query, params)
        except Exception as exc:
            self.logger.error(f"Database error executing '{query}': {exc}")
            raise
