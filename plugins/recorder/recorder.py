import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin


def _get_recorder_router():
    return APIRouter(prefix="/api/plugins/recorder", tags=["recorder"])


def convert_to_wav(input_data: bytes, target_sample_rate: int = 44100) -> bytes:
    """Convert audio data to WAV format using ffmpeg."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as input_file:
            input_file.write(input_data)
            input_file_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
            output_file_path = output_file.name
        
        # Convert to WAV: 44.1kHz, 16-bit, mono
        cmd = [
            'ffmpeg',
            '-i', input_file_path,
            '-ar', str(target_sample_rate),  # Sample rate
            '-ac', '1',                      # Mono
            '-acodec', 'pcm_s16le',          # 16-bit PCM
            '-y',                            # Overwrite output
            output_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
        
        with open(output_file_path, 'rb') as f:
            wav_data = f.read()
        
        return wav_data
    
    finally:
        # Clean up temporary files
        try:
            Path(input_file_path).unlink(missing_ok=True)
            Path(output_file_path).unlink(missing_ok=True)
        except:
            pass


class Recorder(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.router: Optional[APIRouter] = None

    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        self.storage_subfolder = self.settings.get("storage_subfolder", "audio")
        self.storage_root = Path(self.plugin_folder) / self.storage_subfolder
        self.storage_root.mkdir(parents=True, exist_ok=True)

        if self.router is None:
            self.router = _get_recorder_router()
            self._register_routes()

        # Ensure FastAPI router is mounted through plugin manager
        fastapi_app = getattr(self.pm, "fastapi_app", None)
        if fastapi_app and not getattr(self, "_router_registered", False):
            fastapi_app.include_router(self.router)
            self._router_registered = True
        elif fastapi_app is None:
            self.logger.warning("FastAPI app not available; recorder endpoints not registered")

        self.is_loaded = True

    def _register_routes(self):
        @self.router.post("/audio")
        async def upload_audio(plugin: str = Form(...), file: UploadFile = File(...)):
            if not plugin or not plugin.strip():
                raise HTTPException(status_code=400, detail="plugin parameter is required")

            plugin = plugin.strip()

            # Accept more audio formats including webm, ogg, mp4
            supported_types = {
                "audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave",
                "audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg",
                "application/octet-stream"
            }
            
            if file.content_type not in supported_types:
                raise HTTPException(status_code=400, detail=f"Unsupported media type: {file.content_type}")

            data = await file.read()
            if not data:
                raise HTTPException(status_code=400, detail="Empty file")

            # Convert to WAV if not already WAV
            if not file.content_type.startswith("audio/wav") and file.content_type != "audio/x-wav":
                try:
                    self.logger.info(f"Converting {file.content_type} to WAV for plugin {plugin} (data size: {len(data)} bytes)")
                    data = convert_to_wav(data, 44100)  # Convert to 44.1kHz, 16-bit, mono
                    self.logger.info(f"Conversion successful, new data size: {len(data)} bytes")
                except Exception as e:
                    self.logger.error(f"Failed to convert audio to WAV: {e}")
                    raise HTTPException(status_code=500, detail=f"Audio conversion failed: {str(e)}")
            else:
                self.logger.info(f"File is already WAV format, skipping conversion (size: {len(data)} bytes)")

            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
            filename = f"{plugin}_{timestamp}.wav"
            plugin_dir = self.storage_root / plugin
            plugin_dir.mkdir(parents=True, exist_ok=True)
            target_path = plugin_dir / filename

            try:
                with target_path.open("wb") as f:
                    f.write(data)
                self.logger.info(f"Successfully saved audio to {target_path}")
            except OSError as exc:
                self.logger.error(f"Failed saving audio to {target_path}: {exc}")
                raise HTTPException(status_code=500, detail="Failed to write file")

            rel_path = target_path.relative_to(self.plugin_folder)
            self.logger.info(f"Relative path: {rel_path}")

            insert_query = (
                "INSERT INTO records (plugin, created_at, filename) VALUES (?, ?, ?)"
            )
            created_at = datetime.utcnow().isoformat()
            self.logger.info(f"Inserting record: plugin={plugin}, created_at={created_at}, filename={rel_path}")
            
            try:
                # Get direct database connection to access lastrowid
                db_manager = self.db
                if db_manager is None:
                    raise HTTPException(status_code=500, detail="Database not available")
                
                # Execute insert with direct connection to get lastrowid
                query = db_manager._prefix_table_names(self.plugin_name, insert_query)
                conn = db_manager._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, (plugin, created_at, str(rel_path)))
                record_id = cursor.lastrowid
                conn.commit()
                self.logger.info(f"Database insertion successful, record ID: {record_id}")
            except Exception as db_exc:
                self.logger.error(f"Database insertion failed: {db_exc}")
                raise HTTPException(status_code=500, detail="Failed to save record to database")

            return JSONResponse(
                {
                    "id": record_id,
                    "plugin": plugin,
                    "created_at": created_at,
                    "filename": str(rel_path),
                }
            )

        @self.router.get("/audio")
        async def list_audio(plugin: Optional[str] = None):
            if plugin:
                rows = self.db_execute_sync(
                    "SELECT id, plugin, created_at, filename FROM records WHERE plugin = ? ORDER BY created_at DESC",
                    (plugin,),
                )
            else:
                rows = self.db_execute_sync(
                    "SELECT id, plugin, created_at, filename FROM records ORDER BY created_at DESC"
                )

            return rows or []

        @self.router.get("/audio/{record_id}")
        async def get_audio(record_id: int):
            rows = self.db_execute_sync(
                "SELECT id, plugin, created_at, filename FROM records WHERE id = ?",
                (record_id,),
            )
            if not rows:
                raise HTTPException(status_code=404, detail="Recording not found")

            row = rows[0]
            return row

        @self.router.get("/audio/{record_id}/file")
        async def download_audio(record_id: int):
            rows = self.db_execute_sync(
                "SELECT filename FROM records WHERE id = ?",
                (record_id,),
            )
            if not rows:
                raise HTTPException(status_code=404, detail="Recording not found")

            rel_path = rows[0]["filename"]
            file_path = Path(self.plugin_folder) / rel_path
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File missing on disk")

            return FileResponse(file_path, media_type="audio/wav", filename=file_path.name)
