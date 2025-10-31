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
import time  # For timestamp


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
        
        # Audio settings - will be updated based on actual input
        self.sample_rate = 48000  # Default to 48kHz to match microphone

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
            self.confidence_threshold_low = self.settings.get("confidence_threshold_low", 0.4)  # Match frontend threshold
            self.buffer_duration = self.settings.get("buffer_duration", 2.0)
            self.min_audio_duration = self.settings.get("min_audio_duration", 1.0)
            self.identification_cooldown = self.settings.get("identification_cooldown", 3.0)
            
            # Initialize audio buffer AFTER settings
            self.logger.info("Initializing audio buffer...")
            buffer_size = int(self.buffer_duration * self.sample_rate)
            self.audio_buffer = deque(maxlen=buffer_size)
            self.logger.info(f"Audio buffer initialized: {buffer_size} samples ({self.buffer_duration}s duration) at {self.sample_rate} Hz")
            
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
    def process_audio_chunk(self, audio_data: bytes, sample_rate: int = 48000):
        """Process incoming audio chunks for real-time speaker identification"""
        # Update sample rate if different from current
        if sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            buffer_size = int(self.buffer_duration * self.sample_rate)
            self.audio_buffer = deque(maxlen=buffer_size)
            self.logger.info(f"Updated audio buffer for new sample rate: {sample_rate} Hz ({buffer_size} samples)")
        
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
            
        self.logger.debug(f"Processing audio chunk: {len(audio_data)} bytes at {sample_rate} Hz")
        
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

        @self.router.post("/identify_speaker")
        async def identify_speaker_endpoint(audio_file: UploadFile = File(...), sample_rate: Optional[int] = None):
            """Receive complete audio file for speaker identification"""
            try:
                # Read audio data from uploaded file
                audio_bytes = await audio_file.read()
                
                # Use provided sample rate or default to 48kHz
                effective_sample_rate = sample_rate if sample_rate is not None else 48000
                
                self.logger.info(f"Processing audio file for speaker identification: {len(audio_bytes)} bytes at {effective_sample_rate} Hz")
                
                # Convert WebM to PCM if needed
                if audio_file.content_type and 'webm' in audio_file.content_type:
                    # Save the uploaded WebM file to plugin's recordings folder
                    timestamp = int(time.time())
                    recordings_dir = os.path.join(self.plugin_folder, "recordings")
                    if not os.path.exists(recordings_dir):
                        os.makedirs(recordings_dir, exist_ok=True)
                    
                    webm_file_path = os.path.join(recordings_dir, f"identification_{timestamp}.webm")
                    with open(webm_file_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    self.logger.info(f"Saved WebM file for speaker identification: {webm_file_path}")
                    
                    # Convert WebM/Opus to raw PCM for speaker identification using FFmpeg
                    pcm_data = await self._convert_webm_to_pcm_ffmpeg(None, effective_sample_rate, webm_file_path)
                    if pcm_data is not None:
                        # Identify speaker from converted PCM data
                        match, score, top_results = self._identify_from_pcm_data(pcm_data)
                        # Send identification result directly to SpeakerID frontend
                        
                        if match and score >= self.confidence_threshold_low:
                            self.send_message_to_frontend({
                                "type": "speaker_identification",
                                "speaker": {
                                    "name": match,
                                    "confidence": score,
                                    "status": "confirmed" if score >= self.confidence_threshold_low else "partial",
                                    "timestamp": time.time()
                                }
                            })
                            self.logger.info(f"Sent speaker identification to frontend: {match} (confidence: {score:.2f})")
                        else:
                            # Low confidence - still send but with unknown status
                            self.send_message_to_frontend({
                                "type": "speaker_identification", 
                                "speaker": {
                                    "name": "unknown",
                                    "confidence": score,
                                    "status": "unknown",
                                    "timestamp": time.time()
                                }
                            })
                            self.logger.debug(f"Sent unknown speaker identification to frontend (confidence: {score:.2f})")
                        
                        return {
                            "status": "success", 
                            "speaker": {
                                "name": match,
                                "confidence": score,
                                "status": "confirmed" if score >= self.confidence_threshold_low else "partial"
                            }, 
                            "top_results": top_results,
                            "sample_rate": 16000,
                            "webm_file": webm_file_path  # Return file path for reference
                        }
                        
                    else:
                        # WebM conversion failed
                        self.logger.error("Failed to convert WebM to PCM")
                        return {"status": "error", "message": "Audio conversion failed"}
                else:
                    # Handle non-WebM files (WAV, etc.)
                    match, score, top_results = self._identify_from_pcm_data(audio_bytes, effective_sample_rate)
                    return {
                        "status": "success", 
                        "speaker": {
                            "name": match,
                            "confidence": score,
                            "status": "confirmed" if score >= self.confidence_threshold_low else "partial"
                        }, 
                        "top_results": top_results,
                        "sample_rate": effective_sample_rate
                    }
                
            except Exception as e:
                self.logger.error(f"Error processing audio file: {e}")
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
    
    async def _convert_webm_to_pcm_ffmpeg(self, webm_data: bytes, input_sample_rate: int, webm_file_path: Optional[str] = None) -> Optional[bytes]:
        """
        Convert WebM/Opus audio data to raw PCM bytes using FFmpeg
        
        Args:
            webm_data: Raw WebM audio data
            input_sample_rate: Input sample rate (usually 48000)
            webm_file_path: Path to existing WebM file (if available)
            
        Returns:
            Raw PCM audio data as bytes (16-bit signed, mono, 16kHz)
        """
        import tempfile
        import asyncio
        import os
        
        try:
            # If WebM file path provided, use it directly instead of creating temp
            if webm_file_path and os.path.exists(webm_file_path):
                webm_path = webm_file_path
                self.logger.debug(f"Using existing WebM file: {webm_path}")
            else:
                # Create temporary file from data
                with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_webm_file:
                    temp_webm_file.write(webm_data)
                    webm_path = temp_webm_file.name
                self.logger.debug(f"Created temporary WebM file: {webm_path}")
            
            # Create temporary WAV output file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Use FFmpeg for conversion
            def convert_with_ffmpeg():
                import subprocess
                cmd = [
                    'ffmpeg', '-y', '-i', webm_path,  # -y to overwrite
                    '-ar', '16000',  # Sample rate 16kHz for SpeechBrain
                    '-ac', '1',      # Mono
                    '-f', 's16le',   # 16-bit little-endian PCM
                    '-loglevel', 'error',  # Reduce verbosity
                    wav_path
                ]
                
                self.logger.debug(f"Running FFmpeg: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, timeout=30)  # Increased timeout
                
                if result.returncode == 0:
                    # Read converted WAV and extract PCM data (skip header)
                    with open(wav_path, 'rb') as f:
                        f.seek(44)  # Skip WAV header
                        pcm_data = f.read()
                        self.logger.debug(f"FFmpeg converted {len(pcm_data)} bytes of PCM")
                        return pcm_data
                else:
                    self.logger.error(f"FFmpeg conversion failed: {result.stderr.decode()}")
                    return None
            
            # Run conversion in executor to avoid blocking
            loop = asyncio.get_event_loop()
            pcm_data = await loop.run_in_executor(None, convert_with_ffmpeg)
            
            if pcm_data:
                self.logger.info(f"Successfully converted WebM to PCM: {len(pcm_data)} bytes")
                return pcm_data
            else:
                self.logger.error("FFmpeg conversion returned no data")
                
        except Exception as e:
            self.logger.error(f"FFmpeg WebM to PCM conversion failed: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
        finally:
            # Clean up temporary files (only if we created them)
            try:
                if 'webm_path' in locals() and (webm_file_path is None or webm_path != webm_file_path):
                    os.unlink(webm_path)
                    self.logger.debug(f"Cleaned up temporary WebM file: {webm_path}")
                if 'wav_path' in locals():
                    os.unlink(wav_path)
                    self.logger.debug("Cleaned up temporary WAV file")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary files: {e}")
        
        return None
    
    def _identify_from_pcm_data(self, pcm_data: bytes, sample_rate: int = 16000) -> tuple:
        """
        Identify speaker from raw PCM data
        
        Args:
            pcm_data: Raw PCM audio data (16-bit signed, little-endian)
            sample_rate: Sample rate of PCM data
            
        Returns:
            tuple: (best_match_name, similarity_score, top_results)
        """
        if self.speaker_system is None or not self.speaker_system_ready:
            return None, 0.0, []
        
        # Convert bytes to numpy array (16-bit PCM)
        audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        try:
            # Identify speaker using SpeechBrain system
            match, confidence, top_results = self.speaker_system.identify_speaker(
                audio_array, 
                sample_rate=sample_rate,
                threshold=self.confidence_threshold_low,  # Use low threshold for identification
                top_k=3
            )
            
            # Prepare results in format expected by frontend
            formatted_results = []
            for name, score in top_results:
                formatted_results.append({"name": name, "score": float(score)})
            
            return match, confidence, formatted_results
            
        except Exception as e:
            self.logger.error(f"Error during speaker identification: {e}")
            return None, 0.0, []
    
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
    
    async def _convert_webm_to_pcm(self, webm_data: bytes, input_sample_rate: int) -> Optional[bytes]:
        """
        Convert WebM/Opus audio data to raw PCM bytes for speaker identification
        
        Args:
            webm_data: Raw WebM audio data
            input_sample_rate: Input sample rate (usually 48000)
            
        Returns:
            Raw PCM audio data as bytes (16-bit signed, mono, 16kHz)
        """
        import tempfile
        import asyncio
        import os
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as webm_file:
                webm_file.write(webm_data)
                webm_path = webm_file.name
            
            # Use pydub for conversion (pure Python approach)
            try:
                from pydub import AudioSegment
                
                # Convert in asyncio executor to avoid blocking
                def convert_with_pydub():
                    # Read WebM file
                    audio = AudioSegment.from_file(webm_path, format="webm")
                    
                    # Convert to mono and 16kHz
                    audio = audio.set_channels(1)
                    audio = audio.set_frame_rate(16000)
                    
                    # Export as raw PCM bytes directly
                    raw_pcm = audio.raw_data
                    return raw_pcm
                
                # Run conversion in executor
                loop = asyncio.get_event_loop()
                pcm_data = await loop.run_in_executor(None, convert_with_pydub)
                
                if pcm_data:
                    self.logger.debug(f"Successfully converted WebM to PCM: {len(pcm_data)} bytes")
                    return pcm_data
                else:
                    self.logger.warning("PyDub conversion returned empty data")
                    
            except ImportError:
                self.logger.warning("pydub not available, using fallback method")
                
                # Fallback: Use basic audio processing with librosa
                try:
                    import librosa
                    
                    def convert_with_librosa():
                        # Load WebM with librosa
                        y, sr = librosa.load(webm_path, sr=16000, mono=True)
                        
                        # Convert float32 to int16 PCM
                        pcm_int16 = (y * 32767).astype(np.int16)
                        return pcm_int16.tobytes()
                    
                    # Run conversion in executor
                    loop = asyncio.get_event_loop()
                    pcm_data = await loop.run_in_executor(None, convert_with_librosa)
                    
                    if pcm_data:
                        self.logger.debug(f"Successfully converted WebM to PCM using librosa: {len(pcm_data)} bytes")
                        return pcm_data
                        
                except ImportError:
                    self.logger.error("Neither pydub nor librosa available for audio conversion")
                    
        except Exception as e:
            self.logger.error(f"WebM to PCM conversion failed: {e}")
            
        finally:
            # Clean up temporary file
            try:
                if 'webm_path' in locals():
                    os.unlink(webm_path)
            except:
                pass
        
        return None
