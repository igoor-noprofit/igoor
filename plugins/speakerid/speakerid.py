from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import re
import time
import asyncio
import shutil
import traceback
import numpy as np
import threading
from pathlib import Path
from collections import deque
from context_manager import context_manager

from fastapi import APIRouter, HTTPException, File, UploadFile
from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from .speechbrain import SpeakerIdentificationSystem
import time  # For timestamp
from types import SimpleNamespace


class Speakerid(Baseplugin):
    # Deterministic-commit policy (Slice 2f). confidence_threshold_high (loaded from
    # settings, 0.62) is the COMMIT bar; these tune how a speaker reaches it.
    COMMIT_MARGIN = 0.08      # fast-path: min lead over the runner-up to commit at once
    COMMIT_VOTES = 3          # slow path: min agreeing detections (majority of the window)
    EVIDENCE_WINDOW = 5       # how many recent detections the evidence window keeps

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
        self.sample_rate = 48000  # Default to actual browser rate
        
        # Speaker ID status
        self.reset_state()
       
    def reset_state(self):
        """Reset internal state for new conversation/session"""
        self.last_speakers = []
        self.last_speaker = SimpleNamespace(id=False,confidence=-10)
        self.reset_last_phrase()
        with self.buffer_lock:
            if self.audio_buffer is not None:
                self.audio_buffer.clear()
        self.is_processing = False
        self.last_identification_time = 0
        self.current_utterance_start = 0
        # Deterministic-commit state: once a speaker is committed, detection LOCKS
        # for the rest of the conversation (cleared here on abandon/reset).
        self.committed_speaker = None
        self.evidence_window = deque(maxlen=self.EVIDENCE_WINDOW)
        self.logger.info("SpeakerID plugin state has been reset")
 
    def reset_last_phrase(self):
        self.last_phrase_speaker = SimpleNamespace(id=False,confidence=-10)
 
    @hookimpl
    def start_recording(self):
        self.reset_last_phrase()
        
    '''
    @hookimpl
    def stop_recording(self):
        self.reset_last_phrase()
    '''
 
    @hookimpl
    def abandon_conversation(self,cause):
        self.reset_state()
        # SEND MESSAGE TO FRONTEND THAT SPEAKERID HAS RESET
        self.send_message_to_frontend({
            "action": "speakerid_reset"
        })

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        # Refresh the privacy gate if our own settings changed (e.g. via the standard
        # settings UI rather than the /voice_profiles endpoint).
        if plugin_name == self.plugin_name and isinstance(new_settings, dict):
            self.voice_profiles_enabled = bool(new_settings.get("voice_profiles_enabled", False))
            self._current_status["voice_profiles_enabled"] = self.voice_profiles_enabled

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
            # Privacy gate: when off, NO mic audio is accepted for identification (asrjs
            # won't post, and the endpoints early-return). Default off — opt-in.
            self.voice_profiles_enabled = bool(self.settings.get("voice_profiles_enabled", False))
            self._current_status["voice_profiles_enabled"] = self.voice_profiles_enabled

            # Ensure DB schema matches the current code (rebuilds a stale people_id-only
            # speakers table, creates records if missing).
            self._migrate_schema()

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
                    # Reflect readiness in the app boot-progress lifecycle.
                    self.mark_ready()
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
        # Privacy gate: when voice profiles are disabled, accept no mic audio.
        if not self.voice_profiles_enabled:
            return {"status": "disabled", "message": "Voice profiles are disabled"}
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
                return {"status": "initializing", "message": "SpeakerID system still initializing"}
            else:
                # Initialization completed but failed
                return {"status": "error", "message": "SpeakerID system failed to initialize"}
        
        # Debug audio chunk reception
        if len(audio_data) < 100:
            self.logger.debug(f"Received small audio chunk: {len(audio_data)} bytes")
            return {"status": "small_chunk", "message": "Audio chunk too small to process"}
            
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
                return {"status": "processed", "message": "Audio chunk processed successfully"}
            
            return {"status": "buffering", "message": f"Buffering audio ({buffer_duration:.1f}s)", "buffer_duration": buffer_duration}
    
    def _process_buffer_for_identification(self, sample_rate: int):
        """Process the current audio buffer for speaker identification"""
        try:
            # LOCKED: a speaker is committed for this conversation — skip the
            # (expensive) identification entirely until abandon/reset clears the lock.
            if self.committed_speaker is not None:
                return

            # Convert buffer to numpy array
            audio_array = np.array(list(self.audio_buffer))

            # Identify speaker
            match, confidence, top_results = self.speaker_system.identify_speaker(
                audio_array,
                sample_rate=sample_rate,
                threshold=self.confidence_threshold_low,  # low bar = "worth showing"
                top_k=3
            )

            self.last_identification_time = time.time()
            self._handle_detection(match, confidence, top_results)
        except Exception as e:
            self.logger.error(f"Error during speaker identification: {e}")
    

    
    def _update_speaker_context(self, speaker_name: str, confidence: float, status: str):
        print("UPDATING SPEAKER CONTEXT with:", speaker_name, confidence, status)
        """Update the context manager with current speaker information"""
        speaker_info = {
            "name": speaker_name if speaker_name else "unknown",
            "confidence": confidence,
            "status": status,
            "timestamp": time.time()
        }
        
        context_manager.update_context("speaker_info", speaker_info)
        
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
            # Always expose the live gate value (init_speaker_system reassigns
            # _current_status without it), so asrjs can rely on this field.
            status["voice_profiles_enabled"] = self.voice_profiles_enabled
            return {
                "type": "speakerid_status",
                **status
            }

        @self.router.post("/voice_profiles")
        async def set_voice_profiles(payload: Dict[str, Any]):
            """Toggle the voice-profiles privacy gate (master switch for mic→server
            identification). Persisted to settings and surfaced via /status."""
            enabled = bool(payload.get("enabled", False))
            self.update_my_settings("voice_profiles_enabled", enabled)
            self.voice_profiles_enabled = enabled
            self._current_status["voice_profiles_enabled"] = enabled
            self.logger.info(f"voice_profiles_enabled set to {enabled}")
            return {"voice_profiles_enabled": enabled}

        @self.router.get("/speakers")
        async def list_speakers():
            rows = self.db_execute_sync("SELECT id, name, freq FROM speakers ORDER BY id ASC") or []
            # Report per-speaker whether a voice profile exists. A name-only speaker
            # (added without recording) has no voices/<name>/ folder → has_voice=False,
            # so it is selectable for manual tagging but not auto-recognized.
            voices_dir = os.path.join(self.plugin_folder, "voices")
            for row in rows:
                speaker_dir = os.path.join(voices_dir, row.get("name", ""))
                has_wav = False
                if row.get("name") and os.path.isdir(speaker_dir):
                    has_wav = any(f.lower().endswith(".wav") for f in os.listdir(speaker_dir))
                row["has_voice"] = has_wav
            return rows

        @self.router.post("/speakers")
        async def add_speaker(payload: Dict[str, Any]):
            name = self._sanitize_name(payload.get("name", ""))
            if not name:
                raise HTTPException(status_code=400, detail="name is required")
            # Name-only by design: no voices/ folder, no embedding. The UNIQUE
            # constraint is a safety net; check first to avoid exception-as-control-flow.
            existing = self.db_execute_sync(
                "SELECT id, name, freq FROM speakers WHERE name = ?", (name,)
            )
            if existing:
                return existing[0]
            self.db_execute_sync("INSERT INTO speakers (name) VALUES (?)", (name,))
            row = self.db_execute_sync(
                "SELECT id, name, freq FROM speakers WHERE name = ?", (name,)
            )
            return row[0] if row else {"id": None, "name": name, "freq": 0}

        @self.router.delete("/speakers/{speaker_id}")
        async def delete_speaker(speaker_id: int):
            rows = self.db_execute_sync("SELECT name FROM speakers WHERE id = ?", (speaker_id,))
            if not rows:
                raise HTTPException(status_code=404, detail=f"No speaker with id {speaker_id}")
            name = rows[0]["name"]
            # Remove enrollment linkage + the speaker row (no ON DELETE CASCADE in the
            # schema, and SQLite FK enforcement is off by default — delete records first).
            self.db_execute_sync("DELETE FROM records WHERE speakers_id = ?", (speaker_id,))
            self.db_execute_sync("DELETE FROM speakers WHERE id = ?", (speaker_id,))
            # Remove the voice folder so recognition stops, then rebuild the index.
            speaker_dir = os.path.join(self.plugin_folder, "voices", name)
            if os.path.isdir(speaker_dir):
                shutil.rmtree(speaker_dir, ignore_errors=True)
            if self.speaker_system is not None and self.speaker_system_ready:
                await asyncio.to_thread(self.speaker_system.rebuild_speaker, name)
                self._current_status["speaker_count"] = len(self.speaker_system.speaker_names)
            return {"id": speaker_id, "name": name, "deleted": True}

        @self.router.post("/records")
        async def attach_record(payload: Dict[str, Any]):
            recorder_id = payload.get("recorder_id")
            speakers_id = payload.get("speakers_id")
            reset = bool(payload.get("reset", False))
            if recorder_id is None or speakers_id is None:
                raise HTTPException(status_code=400, detail="recorder_id and speakers_id are required")

            # Resolve the speaker's canonical name (= folder name = pkl key = display name).
            speaker_rows = self.db_execute_sync(
                "SELECT name FROM speakers WHERE id = ?", (speakers_id,)
            )
            if not speaker_rows:
                raise HTTPException(status_code=404, detail=f"No speaker with id {speakers_id}")
            speaker_name = speaker_rows[0]["name"]

            # Link the recorder audio to this speaker (unchanged record linkage).
            self.db_execute_sync(
                "INSERT INTO records (recorder_id, speakers_id) VALUES (?, ?)",
                (recorder_id, speakers_id),
            )
            row = self.db_execute_sync(
                "SELECT id, recorder_id, speakers_id FROM records ORDER BY id DESC LIMIT 1"
            )
            record = row[0] if row else {
                "id": None, "recorder_id": recorder_id, "speakers_id": speakers_id
            }

            # Close the enrollment→embedding loop: copy the recorder WAV into
            # voices/<name>/ and rebuild embeddings from all of that speaker's samples.
            enrolled = False
            warning = None
            try:
                wav_src = self._resolve_recorder_wav(recorder_id)
                speaker_dir = os.path.join(self.plugin_folder, "voices", speaker_name)
                os.makedirs(speaker_dir, exist_ok=True)
                if reset:
                    # Re-record: replace the previous voice profile with a fresh one.
                    # Clear old samples so enroll only re-processes the new set — keeps
                    # saves fast (otherwise the folder grows and each save re-processes all).
                    for old in Path(speaker_dir).glob("*.wav"):
                        try:
                            old.unlink()
                        except OSError:
                            pass
                    self.logger.info(f"Re-record for '{speaker_name}': cleared previous samples")
                dest = os.path.join(speaker_dir, f"{recorder_id}_{int(time.time())}.wav")
                shutil.copyfile(str(wav_src), dest)
                self.logger.info(f"Enrolling '{speaker_name}': copied recorder audio to {dest}")

                if self.speaker_system is not None and self.speaker_system_ready:
                    await asyncio.to_thread(self.speaker_system.rebuild_speaker, speaker_name)
                    enrolled = True
                    count = len(self.speaker_system.speaker_names)
                    self._current_status.update({
                        "status": "ready",
                        "speaker_count": count,
                        "message": f"Ready - {count} speakers enrolled",
                        "timestamp": time.time(),
                    })
                    self.logger.info(f"Enrollment complete for '{speaker_name}' ({count} speaker(s) indexed)")
                else:
                    warning = "Speaker system not ready; WAV saved, will enroll on next startup"
                    self.logger.warning(warning)
            except HTTPException:
                raise
            except Exception as exc:
                warning = f"Enrollment failed: {exc}"
                self.logger.error(warning)

            return {**record, "speaker": speaker_name, "enrolled": enrolled, "warning": warning}


        @self.router.get("/records")
        async def list_records():
            rows = self.db_execute_sync(
                "SELECT id, recorder_id, speakers_id FROM records ORDER BY id DESC"
            ) or []
            return rows

        @self.router.post("/identify_speaker")
        async def identify_speaker_endpoint(audio_file: UploadFile = File(...), sample_rate: Optional[int] = None):
            """Receive complete audio file for speaker identification"""
            # Privacy gate: accept no mic audio when voice profiles are disabled.
            if not self.voice_profiles_enabled:
                raise HTTPException(status_code=403, detail="Voice profiles are disabled")
            try:
                # Read audio data from uploaded file
                audio_bytes = await audio_file.read()
                
                # Use provided sample rate or default to 48kHz (frontend sends actual browser rate)
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
                    # Note: ASR frontend now sends 16kHz directly, so this conversion path may not be used
                    pcm_data = await self._convert_webm_to_pcm_ffmpeg(None, effective_sample_rate, webm_file_path)
                    if pcm_data is not None:
                        # Identify speaker from converted PCM data
                        match, score, top_results = self._identify_from_pcm_data(pcm_data)
                        # Send identification result directly to SpeakerID frontend
                       
                        # Accumulate → commit → lock policy (handles tentative display,
                        # commit, and locking). Replaces the old flip-prone inline logic.
                        self._handle_detection(match, score, top_results)
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

        @self.router.post("/process_audio_chunk")
        async def process_audio_chunk_endpoint(audio_file: UploadFile = File(...), sample_rate: Optional[int] = None):
            """Receive audio chunk for real-time speaker identification"""
            # Privacy gate: accept no mic audio (and write no debug chunk) when disabled.
            if not self.voice_profiles_enabled:
                raise HTTPException(status_code=403, detail="Voice profiles are disabled")
            try:
                # Read audio data from uploaded file
                audio_bytes = await audio_file.read()
                
                # Use provided sample rate or default to 48kHz (actual browser rate)
                effective_sample_rate = sample_rate if sample_rate is not None else 48000
                
                self.logger.debug(f"Processing audio chunk for speaker identification: {len(audio_bytes)} bytes at {effective_sample_rate} Hz")
                
                # Convert WebM to PCM if needed
                if audio_file.content_type and 'webm' in audio_file.content_type:
                    # Save the uploaded WebM file to plugin's recordings folder
                    timestamp = int(time.time())
                    recordings_dir = os.path.join(self.plugin_folder, "recordings")
                    if not os.path.exists(recordings_dir):
                        os.makedirs(recordings_dir, exist_ok=True)
                    
                    webm_file_path = os.path.join(recordings_dir, f"chunk_{timestamp}.webm")
                    with open(webm_file_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    self.logger.debug(f"Saved WebM chunk file: {webm_file_path}")
                    
                    # Convert WebM/Opus to raw PCM for speaker identification using FFmpeg
                    pcm_data = await self._convert_webm_to_pcm_ffmpeg(None, effective_sample_rate, webm_file_path)
                    if pcm_data is not None:
                        # Process chunk using the existing hook method logic
                        result = self.process_audio_chunk(pcm_data, effective_sample_rate)
                        return {
                            "status": "success",
                            "chunk_result": result,
                            "sample_rate": 16000,
                            "chunk_file": webm_file_path
                        }
                    else:
                        # WebM conversion failed
                        self.logger.error("Failed to convert WebM chunk to PCM")
                        return {"status": "error", "message": "Audio conversion failed"}
                else:
                    # Handle non-WebM files (WAV, etc.) directly
                    result = self.process_audio_chunk(audio_bytes, effective_sample_rate)
                    return {
                        "status": "success",
                        "chunk_result": result,
                        "sample_rate": effective_sample_rate
                    }
                
            except Exception as e:
                self.logger.error(f"Error processing audio chunk: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _handle_detection(self, match, score, top_results):
        """Apply the accumulate → commit → lock policy to one identification result.

        - confidence_threshold_low  (0.45): a candidate is worth showing as TENTATIVE
          in the topbar — but is NEVER injected into the LLM context.
        - confidence_threshold_high (0.62): the COMMIT bar. Once a speaker is the
          stable majority of the evidence window AND its mean score clears it, COMMIT:
          inject the name into the LLM context and LOCK further detection until reset.
        - Fast path: a single detection ≥ _high with a clear runner-up margin commits
          at once, without waiting for the window to fill.

        Replaces the old 'latest higher score wins' logic, which flipped between
        speakers mid-conversation and could persist the wrong one.
        """
        # LOCKED: a speaker is already committed for this conversation — ignore
        # further detections until abandon_conversation() / reset_state().
        if self.committed_speaker is not None:
            return

        # Nothing usable above the low bar → tentative "unknown", no name injected.
        if not match or score < self.confidence_threshold_low:
            self._send_tentative(None, score)
            return

        runner_up_score = top_results[1][1] if len(top_results) > 1 else 0.0

        # Fast path: one strong, clearly-best detection commits immediately.
        if score >= self.confidence_threshold_high and (score - runner_up_score) >= self.COMMIT_MARGIN:
            self._commit(match, score)
            return

        # Slow path: accumulate evidence, look for a stable majority above the bar.
        self.evidence_window.append((match, score))
        votes = {}
        scores_by_name = {}
        for name, sc in self.evidence_window:
            votes[name] = votes.get(name, 0) + 1
            scores_by_name.setdefault(name, []).append(sc)
        for name, count in votes.items():
            if count >= self.COMMIT_VOTES:
                mean_score = sum(scores_by_name[name]) / len(scores_by_name[name])
                if mean_score >= self.confidence_threshold_high:
                    self._commit(name, mean_score)
                    return

        # No commit yet — show the most-seen candidate as tentative (no LLM injection).
        best_name = max(votes, key=lambda k: votes[k])
        self._send_tentative(best_name, score)

    def _commit(self, name, score):
        """Lock in the committed speaker for this conversation: inject it into the
        LLM context (only committed speakers reach the model), notify the frontend
        as confirmed, and lock further detection."""
        self.committed_speaker = name
        self.last_speaker.id = name
        self.last_speaker.confidence = score
        self.last_phrase_speaker.id = name
        self.last_phrase_speaker.confidence = score
        self.is_processing = False
        self.logger.info(
            f"Speaker COMMITTED: {name} (score {score:.2f}) — detection locked for this conversation"
        )
        # _update_speaker_context updates context_manager["speaker_info"] AND pushes
        # the confirmed speaker to the frontend in one message.
        self._update_speaker_context(name, score, "confirmed")

    def _send_tentative(self, name, score):
        """Show a tentative (unconfirmed) candidate in the topbar WITHOUT injecting a
        name into the LLM context. name=None ⇒ unknown/listening."""
        self.last_speaker.id = name
        self.last_speaker.confidence = score
        self.send_message_to_frontend({
            "type": "speaker_identification",
            "speaker": {
                "name": name or "unknown",
                "confidence": score,
                "status": "partial" if name else "unknown",
                "timestamp": time.time()
            }
        })
                
           
        
    def _migrate_schema(self):
        """Ensure speakers/records tables match the current schema (AUTOINCREMENT).

        Two concerns:
        1. `CREATE TABLE IF NOT EXISTS` (run by the base DB init) won't add columns to a
           table an older install already created — a stale people_id-only `speakers`
           table silently breaks every name/freq query.
        2. `INTEGER PRIMARY KEY` WITHOUT AUTOINCREMENT REUSES ids after a delete. Once
           `conversation_threads.speakers_id` references a speaker (Phase 4), a reused id
           would point conversations at the wrong person. AUTOINCREMENT guarantees ids
           are never reused.

        Detect either and rebuild — preserving existing rows when the columns are
        compatible (rename → create → copy → drop). Fully-qualified names because the
        auto-prefixer only handles FROM/INTO, not DROP/ALTER/PRAGMA.
        """
        def ensure(table, create_sql, required_cols, copy_cols):
            row = self.db_execute_sync(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            cur = (row[0]["sql"] if row else "").upper()
            if row and all(c in cur for c in required_cols) and ("AUTOINCREMENT" in cur):
                return  # already correct
            if row:
                self.logger.warning(f"speakerid: upgrading '{table}' schema (was: {row[0]['sql']})")
            # Preserve rows only if the required columns already exist; else rebuild empty.
            can_copy = bool(row) and all(c in cur for c in required_cols)
            if can_copy:
                self.db_execute_sync(f"ALTER TABLE {table} RENAME TO {table}__old")
            else:
                self.db_execute_sync(f"DROP TABLE IF EXISTS {table}")
            self.db_execute_sync(create_sql)
            if can_copy:
                self.db_execute_sync(
                    f"INSERT INTO {table} ({copy_cols}) SELECT {copy_cols} FROM {table}__old"
                )
                self.db_execute_sync(f"DROP TABLE {table}__old")
            self.logger.info(f"speakerid: '{table}' ensured (AUTOINCREMENT, ids never reused)")

        try:
            spk = f"{self.plugin_name}_speakers"
            rec = f"{self.plugin_name}_records"
            ensure(spk,
                   f"CREATE TABLE {spk} (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, freq INTEGER DEFAULT 0)",
                   ["NAME", "FREQ"],
                   "id, name, freq")
            ensure(rec,
                   f"CREATE TABLE {rec} (id INTEGER PRIMARY KEY AUTOINCREMENT, recorder_id INTEGER NOT NULL, speakers_id INTEGER NOT NULL)",
                   ["RECORDER_ID", "SPEAKERS_ID"],
                   "id, recorder_id, speakers_id")
        except Exception as e:
            self.logger.error(f"speakerid: schema migration failed: {e}")

    def _sanitize_name(self, raw) -> str:
        """Normalize a person name into the single canonical identity key: it becomes
        the speakers.name, the voices/<name>/ folder, the pkl key, and the displayed
        name. Collapse whitespace, strip filesystem-illegal chars and leading dots;
        return '' (→ rejected by callers) for empty/whitespace-only input.
        """
        if raw is None:
            return ""
        name = str(raw).strip()
        name = re.sub(r"\s+", " ", name)               # collapse internal whitespace
        name = re.sub(r'[\\/:\*\?"<>\|]', "", name)    # filesystem-illegal / path separators
        name = name.lstrip(".")                         # no hidden files / ../ tricks
        return name.strip()

    def _resolve_recorder_wav(self, recorder_id):
        """Resolve the on-disk WAV path for a recorder record, in-process (no HTTP).
        Mirrors plugins/biorecorder/biorecorder.py:_generate_voice_sample: look up the
        recorder plugin instance via self.pm.plugins, read its records table with the
        recorder's own db_execute_sync (so table prefixing is correct), then resolve
        Path(recorder.plugin_folder) / filename. Raises HTTPException on any failure.
        """
        recorder = next(
            (p for p in self.pm.plugins if getattr(p, "plugin_name", None) == "recorder"),
            None,
        )
        if recorder is None:
            raise HTTPException(status_code=409, detail="Recorder plugin is not loaded; cannot fetch audio")
        rows = recorder.db_execute_sync(
            "SELECT filename FROM records WHERE id = ?", (recorder_id,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Recorder record {recorder_id} not found")
        wav_path = Path(recorder.plugin_folder) / rows[0]["filename"]
        if not wav_path.exists():
            raise HTTPException(status_code=404, detail=f"Recorder audio file missing on disk: {rows[0]['filename']}")
        return wav_path

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
