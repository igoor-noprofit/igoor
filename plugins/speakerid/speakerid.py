from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import time
import traceback
import numpy as np
import threading
from collections import deque
from context_manager import context_manager

from fastapi import APIRouter, HTTPException, File, UploadFile
from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from .speechbrain import SpeakerIdentificationSystem


class Speakerid(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.router: Optional[APIRouter] = None
        
        # Log instantiation immediately
        self.logger.info("SpeakerID plugin __init__ called - class instantiated")
        
        # Speaker identification components
        self.speaker_system = None
        self.audio_buffer = None
        self.buffer_lock = threading.Lock()
        
        # Processing state
        self.is_processing = False
        self.last_identification_time = 0
        self.current_utterance_start = 0
        
        # Ready status tracking
        self.speaker_system_ready = False
        self.initialization_complete = False
        self._current_status = {
            "status": "not_initialized",
            "message": "SpeakerID not yet initialized",
            "timestamp": time.time()
        }
        
        # Settings (will be loaded in startup)
        self.confidence_threshold_high = 0.7
        self.confidence_threshold_low = 0.5
        self.buffer_duration = 2.0
        self.min_audio_duration = 1.0
        self.identification_cooldown = 3.0

    @hookimpl
    def startup(self):
        """Synchronous startup hook (definitely called)"""
        try:
            self.logger.info("SpeakerID plugin startup method called (sync)")
            
            # Load settings FIRST
            self.logger.info("Loading plugin settings...")
            self.settings = self.get_my_settings()
            self.logger.info(f"Settings loaded successfully: {type(self.settings)}")
            
            self.confidence_threshold_high = self.settings.get("confidence_threshold_high", 0.7)
            self.confidence_threshold_low = self.settings.get("confidence_threshold_low", 0.5)
            self.buffer_duration = self.settings.get("buffer_duration", 2.0)
            self.min_audio_duration = self.settings.get("min_audio_duration", 1.0)
            self.identification_cooldown = self.settings.get("identification_cooldown", 3.0)
            
            # Initialize audio buffer AFTER settings
            self.logger.info("Initializing audio buffer...")
            sample_rate = 16000  # Standard for speech recognition
            buffer_size = int(self.buffer_duration * sample_rate)
            self.audio_buffer = deque(maxlen=buffer_size)
            self.logger.info(f"Audio buffer initialized: {buffer_size} samples ({self.buffer_duration}s duration)")
            
            # Initialize speaker identification system
            voices_dir = os.path.join(self.plugin_folder, "voices")
            embeddings_file = os.path.join(self.plugin_folder, "speaker_embeddings.pkl")
            
        
            # Create voices directory if it doesn't exist
            if not os.path.exists(voices_dir):
                os.makedirs(voices_dir, exist_ok=True)
                self.logger.info(f"Created voices directory: {voices_dir}")
            
            # Initialize speaker identification system in background thread
            self.logger.info("Initializing SpeechBrain system...")
            
            def init_speaker_system():
                try:
                    self.speaker_system = SpeakerIdentificationSystem(
                        voices_dir=voices_dir, 
                        embeddings_file=embeddings_file,
                        plugin_dir=self.plugin_folder  # Pass plugin folder for model storage
                    )
                    self.speaker_system_ready = True
                    self.initialization_complete = True
                    
                    speaker_count = len(self.speaker_system.speaker_names) if self.speaker_system.speaker_names else 0
                    self.logger.info(f"SpeakerID plugin initialized with {speaker_count} enrolled speakers")
                    
                    # Store status for frontend to fetch later
                    self._current_status = {
                        "status": "ready",
                        "speaker_count": speaker_count,
                        "message": f"Ready - {speaker_count} speakers enrolled",
                        "timestamp": time.time()
                    }
                except Exception as e:
                    self.logger.error(f"Failed to initialize speaker system: {e}")
                    self.initialization_complete = True
                    self.speaker_system_ready = False
                    
                    # Store error status for frontend to fetch later
                    self._current_status = {
                        "status": "error",
                        "error": str(e),
                        "message": "Failed to initialize speaker identification",
                        "timestamp": time.time()
                    }
            
            # Start initialization in background thread to avoid blocking
            import threading
            init_thread = threading.Thread(target=init_speaker_system, daemon=True)
            init_thread.start()
            self.logger.info("SpeechBrain initialization started in background thread")
            
            # Initialize default status
            self._current_status = {
                "status": "loading",
                "message": "Initializing speaker identification system...",
                "timestamp": time.time()
            }
            
            self._ensure_router()
            fastapi_app = getattr(self.pm, "fastapi_app", None)
            self.logger.info(f"FastAPI app available: {fastapi_app is not None}")
            self.logger.info(f"Router registered: {getattr(self, '_router_registered', False)}")
            
            if fastapi_app and not getattr(self, "_router_registered", False):
                fastapi_app.include_router(self.router)
                self._router_registered = True
            elif fastapi_app is None:
                self.logger.warning("FastAPI app not available; speakerid endpoints not registered")
            
            self.is_loaded = True
            self.logger.info("SpeakerID plugin startup completed successfully (sync)")
            
        except Exception as e:
            self.logger.error(f"SpeakerID plugin startup failed: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.is_loaded = False
            # Initialize minimal state to prevent crashes
            self.speaker_system = None
            self.audio_buffer = deque(maxlen=32000)

    @hookimpl
    def process_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000):
        """Process incoming audio chunks for real-time speaker identification"""
        # Check if speaker system is ready
        if self.speaker_system is None or not self.speaker_system_ready:
            if not self.initialization_complete:
                # Still initializing
                return {"status": "initializing"}
            else:
                # Initialization completed but failed
                return {"status": "error"}
            return
        
        # Debug audio chunk reception
        if len(audio_data) < 100:
            self.logger.debug(f"Received small audio chunk: {len(audio_data)} bytes")
            return
            
        self.logger.debug(f"Processing audio chunk: {len(audio_data)} bytes")
        
        # Convert bytes to numpy array (16-bit PCM)
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        with self.buffer_lock:
            # Add to buffer
            chunk_samples = len(audio_array)
            for sample in audio_array:
                self.audio_buffer.append(sample)
            
            # Check if we have enough audio and should process
            buffer_duration = len(self.audio_buffer) / sample_rate
            current_time = time.time()
            
            # Start new utterance if not processing
            if not self.is_processing and buffer_duration >= self.min_audio_duration:
                self.current_utterance_start = current_time
                self.is_processing = True
                self.logger.debug("Started new utterance processing")
            
            # Process if we're in an utterance and enough time has passed
            if (self.is_processing and 
                buffer_duration >= self.min_audio_duration and
                current_time - self.last_identification_time >= self.identification_cooldown):
                
                self._process_buffer_for_identification(sample_rate)
    
    def _process_buffer_for_identification(self, sample_rate: int):
        """Process the current audio buffer for speaker identification"""
        try:
            # Convert buffer to numpy array
            audio_array = np.array(list(self.audio_buffer))
            
            # Identify speaker
            match, confidence, top_results = self.speaker_system.identify_speaker(
                audio_array, 
                sample_rate=sample_rate,
                threshold=self.confidence_threshold_low,  # Use low threshold for initial processing
                top_k=3
            )
            
            self.last_identification_time = time.time()
            
            # Handle different confidence levels
            if confidence >= self.confidence_threshold_high:
                # High confidence - confirmed identification
                self._update_speaker_context(match, confidence, "confirmed")
                self.is_processing = False
                self.logger.info(f"Speaker confirmed: {match} (confidence: {confidence:.2f})")
                
            elif confidence >= self.confidence_threshold_low:
                # Medium confidence - partial identification, continue processing
                self._update_speaker_context(match, confidence, "partial")
                self.logger.debug(f"Speaker partially identified: {match} (confidence: {confidence:.2f})")
                
            else:
                # Low confidence - unknown speaker, continue processing
                self._update_speaker_context(None, confidence, "unknown")
                self.logger.debug(f"Speaker unknown (confidence: {confidence:.2f})")
                
        except Exception as e:
            self.logger.error(f"Error during speaker identification: {e}")
    
    def _update_speaker_context(self, speaker_name: str, confidence: float, status: str):
        """Update the context manager with current speaker information"""
        speaker_info = {
            "name": speaker_name if speaker_name else "unknown",
            "confidence": confidence,
            "status": status,
            "timestamp": time.time()
        }
        
        context_manager.update_context("current_speaker", speaker_info)
        
        # Send update to frontend
        self.send_message_to_frontend({
            "type": "speaker_identification",
            "speaker": speaker_info
        })

    def _ensure_router(self):
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/speakerid", tags=["speakerid"])

        @self.router.get("/status")
        async def get_status():
            """Get the current status of the speaker identification system"""
            status = self.get_current_status()
            return {
                "type": "speakerid_status",
                **status
            }

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

        @self.router.post("/process_audio")
        async def process_audio_endpoint(audio_data: UploadFile = File(...)):
            """Receive audio chunks for real-time speaker identification"""
            try:
                # Read audio data from uploaded file
                audio_bytes = await audio_data.read()
                
                # Forward to existing hook implementation
                result = await self.pm.trigger_hook(
                    "process_audio_chunk", 
                    audio_data=audio_bytes, 
                    sample_rate=16000
                )
                
                return {"status": "received", "result": result}
                
            except Exception as e:
                self.logger.error(f"Error processing audio in endpoint: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def db_execute_sync(self, query: str, params: tuple = ()):
        try:
            return super().db_execute_sync(query, params)
        except Exception as exc:
            self.logger.error(f"Database error executing '{query}': {exc}")
            raise
    
    def get_current_status(self):
        """Get the current status of the speaker identification system"""
        return self._current_status.copy()
    
    def get_status_summary(self):
        """Get a human-readable status summary"""
        status = self._current_status.get("status", "unknown")
        message = self._current_status.get("message", "No message")
        
        if status == "ready":
            speaker_count = self._current_status.get("speaker_count", 0)
            return f"Ready - {speaker_count} speakers enrolled"
        elif status == "loading":
            return "Loading speaker identification system..."
        elif status == "error":
            return f"Error: {message}"
        else:
            return message
