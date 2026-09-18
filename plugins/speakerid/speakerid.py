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

from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from types import SimpleNamespace


class Speakerid(Baseplugin):
    # Deterministic-commit policy (Slice 2f). confidence_threshold_high (loaded from
    # settings, 0.51) is the COMMIT bar; these tune how a speaker reaches it.
    COMMIT_MARGIN = 0.08      # fast-path: min lead over the runner-up to commit at once
    COMMIT_VOTES = 3          # slow path: min agreeing detections (majority of the window)
    EVIDENCE_WINDOW = 5       # how many recent detections the evidence window keeps
    SILENCE_RMS = 0.005       # buffers below this RMS are silence/noise — skip the forward pass

    # Folder-name hardening: the speaker's name becomes the voices/<name>/ folder.
    RESERVED_NAMES = frozenset(  # Windows device names — unusable as folders (with any extension)
        {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
        | {f"COM{i}" for i in range(1, 10)}
        | {f"LPT{i}" for i in range(1, 10)}
    )
    MAX_NAME_LEN = 100        # the APPDATA path prefix + MAX_PATH leave ~190 chars; 100 is plenty for a person name

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
        # One inference at a time: chunks can now be processed off the event loop,
        # so a slow forward pass must not overlap the next chunk's pass.
        self._infer_busy = False
        # Last (name, status) pushed as TENTATIVE — used to dedup identical pushes.
        self._last_tentative_push = None
        
        # Ready status tracking
        self.speaker_system_ready = False
        self.initialization_complete = False
        self._init_thread_running = False
        self._current_status = {
            "status": "not_initialized",
            "message": "SpeakerID not yet initialized",
            "timestamp": time.time()
        }
        
        # Settings (will be loaded in startup) — defaults mirror settings.json
        self.confidence_threshold_high = 0.51
        self.confidence_threshold_low = 0.45
        self.buffer_duration = 2.0
        self.min_audio_duration = 1.0
        self.identification_cooldown = 3.0
        # Pre-warm staleness: a pre-warmed speaker must be re-confirmed by fresh
        # detections within this many seconds, or it reverts to unknown. Without
        # it, silence never clears a pre-warm (no-match results don't touch the
        # context), so a name detected hours ago could be promoted+locked at the
        # next conversation open.
        self.prewarm_ttl = 30.0
        self._last_prewarm_refresh = 0.0

        # Audio settings - will be updated based on actual input
        self.sample_rate = 16000  # chunks arrive pre-downsampled to 16kHz by the asrjs worklet
        self._buffer_max_bytes = int(self.buffer_duration * self.sample_rate) * 2
        
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
        self._infer_busy = False
        self._last_tentative_push = None
        self._last_prewarm_refresh = 0.0
        # Deterministic-commit state: once a speaker is committed, detection LOCKS
        # for the rest of the conversation (cleared here on abandon/reset).
        self.committed_speaker = None
        self.evidence_window = deque(maxlen=self.EVIDENCE_WINDOW)
        # Continuous pre-warm gate: commits only LOCK when a conversation is active.
        # Init and abandon both route through reset_state, so this covers both — the
        # flag flips True on the first add_msg_to_conversation of a new conversation.
        self.conversation_active = False
        # TTS pause: while the app speaks (pause_asr), identification is suspended so the
        # mic's capture of the synthesized voice isn't identified. Cleared here (init/abandon)
        # so a pause with no matching restart can't stick.
        self.identification_paused = False
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
    def add_msg_to_conversation(self, msg, author, msg_input):
        """Conversation-START signal (fires on the first message of each conversation).
        Switches from continuous pre-warm mode (unlocked) to conversation mode. Gives the
        detection state machine a fresh acoustic slate, then PROMOTES any pre-warmed
        speaker to CONFIRMED: the caregiver's opening utterance was detected before the
        conversation opened (as a pre-warm), so carry that recognition in as the
        conversation's speaker rather than requiring a fresh in-conversation commit.
        Manual correction via the topbar (/set_speaker) still overrides this at any time,
        even while locked. Idempotent: only acts on the first message."""
        if self.conversation_active:
            return
        # A stale pre-warm must not be promoted: expire it first. Silence never
        # re-confirms anything, and chunks may have stopped entirely (mic off,
        # asrjs down) while the room was quiet — so the promotion path can't rely
        # on the chunk heartbeat having caught the expiry.
        self._expire_stale_prewarm()
        self.conversation_active = True
        self.evidence_window = deque(maxlen=self.EVIDENCE_WINDOW)   # fresh voting
        with self.buffer_lock:
            if self.audio_buffer is not None:
                self.audio_buffer.clear()                            # drop gap audio
        self.is_processing = False
        # Promote a pre-warmed (unlocked) speaker to CONFIRMED now that the conversation
        # is open. The opening utterance was detected pre-conversation (pre-warm), so
        # treat that as the conversation's speaker instead of waiting for a fresh commit.
        # If it's wrong, the caregiver corrects it in the topbar — /set_speaker overrides
        # the lock at any time.
        info = (context_manager.get_context() or {}).get("speaker_info") or {}
        pw_name = info.get("name")
        if pw_name and pw_name != "unknown" and info.get("status") == "prewarmed":
            score = self.last_speaker.confidence if getattr(self.last_speaker, "id", None) == pw_name else 1.0
            self.committed_speaker = pw_name                         # LOCK for this conversation
            self._update_speaker_context(pw_name, score, "confirmed")
            self.logger.info(
                f"Pre-warmed speaker '{pw_name}' PROMOTED to CONFIRMED at conversation open "
                f"(score {score:.2f}) — detection locked"
            )

    @hookimpl
    def abandon_conversation(self,cause):
        self.reset_state()
        # SEND MESSAGE TO FRONTEND THAT SPEAKERID HAS RESET
        self.send_message_to_frontend({
            "action": "speakerid_reset"
        })

    @hookimpl
    def pause_asr(self):
        # TTS is speaking: pause identification. The mic captures the app's synthesized
        # voice, which can't match an enrolled speaker — process_audio_chunk discards
        # chunks while paused (no buffer work, no model inference).
        self.identification_paused = True

    @hookimpl
    def restart_asr(self, force_ready):
        # TTS finished: resume identification. No buffer clear — the pause gate skipped
        # appends, so the buffer holds clean pre-TTS audio and rolls over on resume.
        self.identification_paused = False

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        # Refresh the privacy gate if our own settings changed (e.g. via the standard
        # settings UI rather than the /voice_profiles endpoint).
        if plugin_name == self.plugin_name and isinstance(new_settings, dict):
            was_enabled = self.voice_profiles_enabled
            self.voice_profiles_enabled = bool(new_settings.get("voice_profiles_enabled", False))
            self._current_status["voice_profiles_enabled"] = self.voice_profiles_enabled
            self.assignment_popup_enabled = bool(new_settings.get("assignment_popup_enabled", False))
            self._current_status["assignment_popup_enabled"] = self.assignment_popup_enabled
            # Lazy enable: switched on at runtime → load SpeechBrain now in the
            # background (no restart). Switching off just closes the gate; the
            # model stays resident until the app restarts.
            if self.voice_profiles_enabled and not was_enabled:
                self._start_speaker_system_init()

    @hookimpl
    def get_current_speaker(self):
        """The current conversation's speaker + how it was identified.

        Always returns a dict {speakers_id, name, method} (never None) so conversation.py
        can persist the identification PATH on conversation_threads.speaker_id_method
        even when no speaker was identified:

            method=1   automatic (speakerid _commit) — speakers_id set
            method=-1  manual topbar click (/set_speaker) — speakers_id set, or NULL
                       if the user explicitly clicked "Unknown"
            method=0   manual post-hoc popup (/thread_speaker) — written directly by
                       conversation.py, never produced here
            method=-2  speakerid active (voice profiles ON) but no match — speakers_id NULL
            method=-3  speakerid deactivated (voice profiles OFF) — speakers_id NULL

        Reads context_manager (set by commit/set_speaker) rather than committed_speaker,
        so it's robust to abandon/reset hook ordering.

        Attribution remains COMMITTED-only: a pre-warmed (unlocked) ambient speaker must
        NOT be attributed to a conversation — e.g. a conversation that never re-commits
        ends Unknown (-2/-3) rather than inheriting whoever was talking in the room. The
        name still reaches the LLM via {dynamic_context} regardless of this filter.
        """
        info = (context_manager.get_context() or {}).get("speaker_info") or {}
        name = info.get("name")
        status = info.get("status")
        manual = info.get("method") == "manual"
        voice_on = bool(getattr(self, "voice_profiles_enabled", False))

        # Manual "Unknown" click (set_speaker with speaker_id=null): a manual action even
        # though no speaker is set. Encoded as -1 with NULL speakers_id.
        if manual and (not name or name == "unknown"):
            return {"speakers_id": None, "name": None, "method": -1}

        # No identified speaker: distinguish "tried and failed" (-2) from "off" (-3).
        if status != "confirmed" or not name or name == "unknown":
            return {"speakers_id": None, "name": None, "method": -2 if voice_on else -3}

        # Confirmed speaker: resolve speakers_id. Manual topbar pick → -1, auto commit → 1.
        rows = self.db_execute_sync("SELECT id FROM speakers WHERE name = ?", (name,))
        if not rows:
            return {"speakers_id": None, "name": name, "method": -1 if manual else 1}
        return {
            "speakers_id": rows[0]["id"],
            "name": name,
            "method": -1 if manual else 1,
        }

    @hookimpl
    def get_context_speaker(self):
        """The speaker currently in context (pre-warmed OR confirmed), for LLM history
        injection. Unlike get_current_speaker this includes pre-warmed speakers, so their
        past conversations are injected from the first LLM call even before a commit.
        Attribution still uses the confirmed-only get_current_speaker."""
        info = (context_manager.get_context() or {}).get("speaker_info") or {}
        name = info.get("name")
        if not name or name == "unknown":
            return None
        rows = self.db_execute_sync("SELECT id FROM speakers WHERE name = ?", (name,))
        if not rows:
            return None
        return {"speakers_id": rows[0]["id"], "name": name}

    @hookimpl
    def get_speaker_name(self, speakers_id):
        """Resolve a speakers_id to the speaker's name, or None."""
        if not speakers_id:
            return None
        try:
            rows = self.db_execute_sync("SELECT name FROM speakers WHERE id = ?", (speakers_id,))
            return rows[0]["name"] if rows else None
        except Exception as e:
            self.logger.error(f"get_speaker_name failed: {e}")
            return None

    @hookimpl
    async def after_conversation_end(self, last_conversation):
        """Bump freq for the conversation's speaker (feeds the topbar's most-frequent
        ordering), then clear speaker_info so the next conversation starts fresh — a
        conversation with no identified speaker is classified Unknown (NULL speakers_id).
        Also fires the opt-in assignment popup when the conversation ended Unknown."""
        spk = self.get_current_speaker()
        lc = last_conversation if isinstance(last_conversation, dict) else {}
        thread_id = lc.get("thread_id")
        self.logger.info(
            f"after_conversation_end: lc_keys={list(lc.keys())}, thread_id={thread_id!r}, "
            f"spk={spk}, popup_enabled={getattr(self, 'assignment_popup_enabled', False)}"
        )
        if spk and spk.get("speakers_id") is not None:
            try:
                self.db_execute_sync("UPDATE speakers SET freq = freq + 1 WHERE id = ?", (spk["speakers_id"],))
            except Exception as e:
                self.logger.warning(f"freq bump failed: {e}")
        # Fallback assignment popup: only when nothing was committed AND the user opted in.
        # Fires only for conversations that end Unknown — well-detected ones never bug the user.
        # (get_current_speaker now always returns a dict; check speakers_id for "no speaker".)
        if getattr(self, 'assignment_popup_enabled', False) and not (spk or {}).get("speakers_id"):
            if thread_id:
                sent = self.send_message_to_frontend({
                    "action": "speakerid_assignment_popup",
                    "thread_id": thread_id
                })
                self.logger.info(f"after_conversation_end: assignment popup sent for thread {thread_id} (ok={sent})")
            else:
                self.logger.warning("after_conversation_end: popup enabled but no thread_id in last_conversation")
        # Clear so a stale speaker doesn't bleed into the next conversation.
        context_manager.update_context("speaker_info", {
            "name": "unknown", "status": "unknown"
        })

    @hookimpl
    async def data_imported(self, backup_path=None, **kwargs):
        """After a data import, voices/ + speaker_embeddings.pkl on disk may have been
        replaced. Rebuild the in-memory index from the restored voices/ so recognition
        works without an app restart (the startup load also covers this once restarted;
        this makes it live). Guarded on the system being ready; if not, startup will
        load the restored voices/."""
        if not self.speaker_system or not self.speaker_system_ready:
            self.logger.info("data_imported: speaker system not ready — restored voices/ load when the system initializes (startup or enabling voice profiles)")
            return
        try:
            await asyncio.to_thread(self.speaker_system.rebuild)
            self._current_status["speaker_count"] = len(self.speaker_system.speaker_names)
            self.logger.info("data_imported: rebuilt speaker embeddings from restored voices/")
        except Exception as e:
            self.logger.warning(f"data_imported: rebuild failed: {e}")

    @hookimpl
    def startup(self):
        """Synchronous startup hook (definitely called)"""
        try:
            self.logger.info("SpeakerID plugin startup method called (sync)")
            
            # Load settings FIRST
            self.logger.info("Loading plugin settings...")
            self.settings = self.get_my_settings()
            self.logger.info(f"Settings loaded successfully: {type(self.settings)}")
            
            self.confidence_threshold_high = self.settings.get("confidence_threshold_high", 0.51)
            self.confidence_threshold_low = self.settings.get("confidence_threshold_low", 0.45)
            self.buffer_duration = self.settings.get("buffer_duration", 2.0)
            self.min_audio_duration = self.settings.get("min_audio_duration", 1.0)
            self.identification_cooldown = self.settings.get("identification_cooldown", 3.0)
            self.prewarm_ttl = self.settings.get("prewarm_ttl", 30.0)
            # Privacy gate: when off, NO mic audio is accepted for identification (asrjs
            # won't post, and the endpoints early-return). Default off — opt-in.
            self.voice_profiles_enabled = bool(self.settings.get("voice_profiles_enabled", False))
            self._current_status["voice_profiles_enabled"] = self.voice_profiles_enabled
            # Opt-in: show a speaker-assignment popup at the end of a conversation that ended
            # Unknown (no committed speaker) — a manual fallback. Default off.
            self.assignment_popup_enabled = bool(self.settings.get("assignment_popup_enabled", False))
            self._current_status["assignment_popup_enabled"] = self.assignment_popup_enabled

            # Ensure DB schema matches the current code (rebuilds a stale people_id-only
            # speakers table, creates records if missing).
            self._migrate_schema()

            # Initialize audio buffer AFTER settings. Rolling int16 byte buffer:
            # appends are memcpys and reads are np.frombuffer — no per-sample
            # Python looping on the hot path.
            self.logger.info("Initializing audio buffer...")
            self._buffer_max_bytes = int(self.buffer_duration * self.sample_rate) * 2
            self.audio_buffer = bytearray()
            self.logger.info(f"Audio buffer initialized: {self._buffer_max_bytes // 2} samples ({self.buffer_duration}s duration) at {self.sample_rate} Hz")
            
            # Initialize speaker identification system
            voices_dir = os.path.join(self.plugin_folder, "voices")
            embeddings_file = os.path.join(self.plugin_folder, "speaker_embeddings.pkl")
            
        
            # Create voices directory if it doesn't exist
            if not os.path.exists(voices_dir):
                os.makedirs(voices_dir, exist_ok=True)
                self.logger.info(f"Created voices directory: {voices_dir}")
            
            if self.voice_profiles_enabled:
                self._start_speaker_system_init(voices_dir, embeddings_file)
            else:
                # SpeechBrain/torch stay unloaded unless voice profiles are enabled
                # (default off): eager loading cost ~100-300 MB of RAM for a feature
                # the privacy gate kept switched off anyway. Enabling them at runtime
                # loads the model lazily — no restart needed.
                self.initialization_complete = True
                self._current_status = {
                    "status": "disabled",
                    "message": "Voice profiles are disabled - speaker recognition not loaded",
                    "timestamp": time.time()
                }
                self.mark_ready()
                self.logger.info("Voice profiles disabled: SpeechBrain not loaded")
            
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
            self.audio_buffer = bytearray()
            self._buffer_max_bytes = 64000

    def _start_speaker_system_init(self, voices_dir=None, embeddings_file=None):
        """Load the SpeechBrain identification system in a background thread.

        Called from startup() when voice profiles are enabled, and lazily when
        they are switched on at runtime (settings_updated hook or the
        /voice_profiles endpoint) — no restart needed. No-op when a load is
        already running or the system is already up."""
        if self._init_thread_running:
            return
        if self.speaker_system is not None and self.speaker_system_ready:
            return
        if voices_dir is None:
            voices_dir = os.path.join(self.plugin_folder, "voices")
        if embeddings_file is None:
            embeddings_file = os.path.join(self.plugin_folder, "speaker_embeddings.pkl")

        self._init_thread_running = True
        self.logger.info("Initializing SpeechBrain system...")
        self._current_status = {
            "status": "loading",
            "message": "Initializing speaker identification system...",
            "timestamp": time.time()
        }

        def init_speaker_system():
            try:
                # Deferred import keeps torch/speechbrain/faiss out of RAM unless
                # the system is actually used (the module-top import used to pull
                # them in at plugin import time).
                from .speechbrain import SpeakerIdentificationSystem
                self.speaker_system = SpeakerIdentificationSystem(
                    voices_dir=voices_dir,
                    embeddings_file=embeddings_file,
                    plugin_dir=self.plugin_folder,  # Pass plugin folder for model storage
                    logger=self.logger
                )
                self.speaker_system_ready = True
                self.initialization_complete = True

                speaker_count = len(self.speaker_system.speaker_names) if self.speaker_system.speaker_names else 0
                self.logger.info(f"SpeakerID plugin initialized with {speaker_count} enrolled speakers")

                # Warm-up pass: absorb torch's lazy init (kernel dispatch, allocator)
                # here in the background so the first real chunk after speech starts
                # doesn't pay it mid-conversation.
                try:
                    self.speaker_system.identify_speaker(
                        np.zeros(16000, dtype=np.float32), sample_rate=16000
                    )
                except Exception as warm_exc:
                    self.logger.warning(f"Warm-up pass failed (non-fatal): {warm_exc}")

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
            finally:
                self._init_thread_running = False

        # Start initialization in background thread to avoid blocking
        init_thread = threading.Thread(target=init_speaker_system, daemon=True)
        init_thread.start()
        self.logger.info("SpeechBrain initialization started in background thread")

    @hookimpl
    def process_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000):
        """Process incoming audio chunks for real-time speaker identification.
        audio_data is raw 16-bit little-endian mono PCM at sample_rate. Runs on the
        caller's thread (the REST endpoint wraps it in asyncio.to_thread), so all
        shared-state mutation happens under buffer_lock."""
        # Privacy gate: when voice profiles are disabled, accept no mic audio.
        if not self.voice_profiles_enabled:
            return {"status": "disabled", "message": "Voice profiles are disabled"}
        # TTS is speaking: the mic captures the app's own synthesized voice, which can't
        # match an enrolled speaker — skip identification (and don't touch the buffer).
        if self.identification_paused:
            return {"status": "paused", "message": "Identification paused during TTS"}

        # Check if speaker system is ready
        if self.speaker_system is None or not self.speaker_system_ready:
            if not self.initialization_complete:
                # Still initializing
                return {"status": "initializing", "message": "SpeakerID system still initializing"}
            else:
                # Initialization completed but failed
                return {"status": "error", "message": "SpeakerID system failed to initialize"}

        # Skip chunks too small to identify.
        if len(audio_data) < 100:
            return {"status": "small_chunk", "message": "Audio chunk too small to process"}

        # Chunk heartbeat: with ~2s chunks this re-checks pre-warm staleness often
        # enough that an aged-out name disappears from the context/topbar within a
        # couple of seconds of the TTL lapsing (silence itself runs no detections).
        self._expire_stale_prewarm()

        with self.buffer_lock:
            if self.audio_buffer is None:
                self.audio_buffer = bytearray()

            # Resize the rolling buffer if the incoming rate changed.
            if sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
                self._buffer_max_bytes = int(self.buffer_duration * sample_rate) * 2
                del self.audio_buffer[:-self._buffer_max_bytes]
                self.logger.info(
                    f"Updated audio buffer for new sample rate: {sample_rate} Hz "
                    f"({self._buffer_max_bytes // 2} samples)"
                )

            # Rolling int16 byte buffer: byte appends are memcpys, and reads below are
            # np.frombuffer — the old per-sample Python deque loop boxed every sample.
            self.audio_buffer.extend(audio_data)
            if len(self.audio_buffer) % 2:
                del self.audio_buffer[-1:]  # stray trailing byte from a truncated upload
            if len(self.audio_buffer) > self._buffer_max_bytes:
                del self.audio_buffer[:-self._buffer_max_bytes]

            # Check if we have enough audio and should process
            buffer_duration = (len(self.audio_buffer) // 2) / sample_rate
            current_time = time.time()

            # Start new utterance if not processing
            if not self.is_processing and buffer_duration >= self.min_audio_duration:
                self.current_utterance_start = current_time
                self.is_processing = True

            # Process if we're in an utterance and enough time has passed.
            # Copy the audio out under the lock; the (slow) inference itself runs
            # with the lock released so the next chunk can buffer meanwhile.
            should_process = (
                self.is_processing
                and buffer_duration >= self.min_audio_duration
                and current_time - self.last_identification_time >= self.identification_cooldown
            )
            audio_array = (
                np.frombuffer(self.audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                if should_process
                else None
            )

        if should_process:
            self._process_buffer_for_identification(audio_array, sample_rate)
            return {"status": "processed", "message": "Audio chunk processed successfully"}

        return {"status": "buffering", "message": f"Buffering audio ({buffer_duration:.1f}s)", "buffer_duration": buffer_duration}

    def _process_buffer_for_identification(self, audio_array: np.ndarray, sample_rate: int):
        """Run speaker identification on one snapshot of the audio buffer (a private
        copy — the buffer lock is NOT held here)."""
        try:
            # LOCKED: a speaker is committed for this conversation — skip the
            # (expensive) identification entirely until abandon/reset clears the lock.
            if self.committed_speaker is not None:
                return

            # One inference at a time: skip (don't queue) while a previous buffer is
            # still being embedded — the next chunk arrives with fresher audio anyway.
            if self._infer_busy:
                self.logger.debug("Identification already in flight — skipping this buffer")
                return

            # Silence/noise gate: an ECAPA embedding of non-speech is meaningless and
            # would burn a forward pass and pollute the evidence window.
            rms = float(np.sqrt(np.mean(np.square(audio_array))))
            if rms < self.SILENCE_RMS:
                self.logger.debug(f"Skipping identification: buffer is silence/noise (RMS {rms:.4f})")
                return

            self._infer_busy = True
            try:
                match, confidence, top_results = self.speaker_system.identify_speaker(
                    audio_array,
                    sample_rate=sample_rate,
                    threshold=self.confidence_threshold_low,  # low bar = "worth showing"
                    top_k=3
                )
            finally:
                self._infer_busy = False

            self.last_identification_time = time.time()
            self._handle_detection(match, confidence, top_results)
        except Exception as e:
            self.logger.error(f"Error during speaker identification: {e}")

    def _expire_stale_prewarm(self):
        """Revert a pre-warmed speaker to unknown when it hasn't been re-confirmed by
        a fresh detection within prewarm_ttl seconds. No-match results and silence
        never touch the context, so without this a pre-warm lingers forever and would
        be promoted + locked at the next conversation open no matter how stale."""
        if self._last_prewarm_refresh <= 0:
            return
        info = (context_manager.get_context() or {}).get("speaker_info") or {}
        name = info.get("name")
        if info.get("status") != "prewarmed" or not name or name == "unknown":
            self._last_prewarm_refresh = 0.0   # pre-warm already gone — drop the timer
            return
        if time.time() - self._last_prewarm_refresh <= self.prewarm_ttl:
            return
        self._last_prewarm_refresh = 0.0
        self.evidence_window.clear()           # stale votes must not seed the next commit
        self.logger.info(
            f"Pre-warmed speaker '{name}' expired — no re-confirming detection within "
            f"{self.prewarm_ttl:.0f}s, reverting to unknown"
        )
        self._update_speaker_context("unknown", 0.0, "unknown")
    

    
    def _update_speaker_context(self, speaker_name: str, confidence: float, status: str, method: str = "auto"):
        """Update the context manager + frontend with current speaker information.
        The LLM-facing context excludes confidence (not needed in the prompt); the
        frontend message keeps it for the topbar display.

        method is the identification PATH: "auto" (speakerid _commit) or "manual"
        (user clicked the topbar /set_speaker). It is threaded through context_manager
        so get_current_speaker can resolve the per-conversation speaker_id_method code
        persisted on conversation_threads. The frontend ignores unknown keys, so adding
        it to the push is safe without a .vue change."""
        ts = time.time()
        name = speaker_name if speaker_name else "unknown"
        # A confirmed/manual push changes the topbar — let the next identical-looking
        # tentative push through even if it matches the last tentative we sent.
        self._last_tentative_push = None
        context_manager.update_context("speaker_info", {
            "name": name,
            "status": status,
            "method": method
        })
        self.send_message_to_frontend({
            "type": "speaker_identification",
            "speaker": {
                "name": name,
                "confidence": confidence,
                "status": status,
                "method": method,
                "timestamp": ts
            }
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
            status["assignment_popup_enabled"] = self.assignment_popup_enabled
            # User's name (IGOOR user / bio_name) so the frontend can build
            # caregiver→user enrollment phrases that address them by name.
            status["bio_name"] = self.settings_manager.get_bio().get("name") or ""
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
            # Lazy enable: load SpeechBrain now if it isn't loaded yet (no restart).
            if enabled:
                self._start_speaker_system_init()
            self.logger.info(f"voice_profiles_enabled set to {enabled}")
            return {"voice_profiles_enabled": enabled}

        @self.router.post("/assignment_popup")
        async def set_assignment_popup(payload: Dict[str, Any]):
            """Toggle the end-of-conversation assignment popup (manual fallback for
            conversations that ended Unknown). Persisted + surfaced via /status."""
            enabled = bool(payload.get("enabled", False))
            self.update_my_settings("assignment_popup_enabled", enabled)
            self.assignment_popup_enabled = enabled
            self._current_status["assignment_popup_enabled"] = enabled
            self.logger.info(f"assignment_popup_enabled set to {enabled}")
            return {"assignment_popup_enabled": enabled}

        @self.router.post("/set_speaker")
        async def set_speaker(payload: Dict[str, Any]):
            """Manually select/correct the speaker for the current conversation.

            speaker_id int  → lock to that speaker (reuses the 2f lock; auto-detection
                               won't override). Works whether or not voice profiles are on.
            speaker_id null → Unknown: CLEAR the lock so auto-detection keeps trying.
                               (A conversation with no identified speaker ends as Unknown.)
            """
            speaker_id = payload.get("speaker_id")
            if speaker_id is None:
                self.committed_speaker = None
                self.last_speaker = SimpleNamespace(id=False, confidence=-10)
                self.last_phrase_speaker = SimpleNamespace(id=False, confidence=-10)
                # Clear the LLM-facing context too (previously missing): so a stale
                # confirmed/pre-warmed speaker can't be attributed after the user
                # explicitly chose Unknown. This also pushes the topbar "unknown" msg.
                self._update_speaker_context("unknown", 0.0, "unknown", method="manual")
                self.logger.info("Speaker set to Unknown — detection unlocked, will keep trying")
                return {"name": "unknown", "manual": True}

            rows = self.db_execute_sync("SELECT name FROM speakers WHERE id = ?", (speaker_id,))
            if not rows:
                raise HTTPException(status_code=404, detail=f"No speaker with id {speaker_id}")
            name = rows[0]["name"]
            # Lock to the chosen speaker (same lock auto-commit uses); never inject 'unknown'.
            self.committed_speaker = name
            self.last_speaker = SimpleNamespace(id=name, confidence=1.0)
            self.last_phrase_speaker = SimpleNamespace(id=name, confidence=1.0)
            self.is_processing = False
            self.send_message_to_frontend({
                "type": "speaker_identification",
                "speaker": {"name": name, "confidence": 1.0, "status": "confirmed",
                            "manual": True, "method": "manual", "timestamp": time.time()}
            })
            self._update_speaker_context(name, 1.0, "confirmed", method="manual")
            self.logger.info(f"Speaker set manually: {name} — detection locked")
            return {"name": name, "manual": True}

        @self.router.get("/speakers")
        async def list_speakers():
            rows = self.db_execute_sync("SELECT id, name, freq FROM speakers ORDER BY id ASC") or []
            # Report per-speaker whether a voice profile exists. A name-only speaker
            # (added without recording) has no voices/<name>/ folder → has_voice=False,
            # so it is selectable for manual tagging but not auto-recognized.
            for row in rows:
                speaker_dir = self._safe_speaker_dir(row.get("name", ""))
                wav_count = 0
                if speaker_dir and os.path.isdir(speaker_dir):
                    wav_count = sum(1 for f in os.listdir(speaker_dir) if f.lower().endswith(".wav"))
                row["has_voice"] = wav_count > 0
                row["sample_count"] = wav_count
            return rows

        @self.router.post("/speakers")
        async def add_speaker(payload: Dict[str, Any]):
            name = self._sanitize_name(payload.get("name", ""))
            if not name:
                raise HTTPException(
                    status_code=400,
                    detail="name is required, reserved, too long, or has no usable characters",
                )
            # Name-only by design: no voices/ folder, no embedding. The UNIQUE
            # constraint is a safety net; check first to avoid exception-as-control-flow.
            # NOCASE: Windows folders are case-insensitive but SQLite UNIQUE is not —
            # "jessica" must reuse the "Jessica" row, not silently share her voice folder.
            existing = self.db_execute_sync(
                "SELECT id, name, freq FROM speakers WHERE name = ? COLLATE NOCASE", (name,)
            )
            if existing:
                return existing[0]
            # Same clash from the other side: a voices/<name>/ folder that arrived
            # without a DB row (e.g. an import) — Windows compares folder names
            # case-insensitively too.
            voices_dir = os.path.join(self.plugin_folder, "voices")
            if os.path.isdir(voices_dir) and any(
                d != name and d.lower() == name.lower() for d in os.listdir(voices_dir)
            ):
                raise HTTPException(
                    status_code=409, detail="a voices folder with a similar name already exists"
                )
            self.db_execute_sync("INSERT INTO speakers (name) VALUES (?)", (name,))
            row = self.db_execute_sync(
                "SELECT id, name, freq FROM speakers WHERE name = ?", (name,)
            )
            # Roster changed — push it: the topbar component fetches speakers once at mount.
            self.send_message_to_frontend({"type": "speakerid_speakers_changed"})
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
            # Only when the name resolves safely inside voices/ (crafted-import guard).
            speaker_dir = self._safe_speaker_dir(name)
            if speaker_dir is None:
                self.logger.warning(f"delete_speaker: unsafe stored name {name!r} — rows deleted, files left alone")
            else:
                if os.path.isdir(speaker_dir):
                    shutil.rmtree(speaker_dir, ignore_errors=True)
                if self.speaker_system is not None and self.speaker_system_ready:
                    await asyncio.to_thread(self.speaker_system.rebuild_speaker, name)
                    self._current_status["speaker_count"] = len(self.speaker_system.speaker_names)
            self.send_message_to_frontend({"type": "speakerid_speakers_changed"})
            return {"id": speaker_id, "name": name, "deleted": True}

        @self.router.post("/reset_voice")
        async def reset_voice(payload: Dict[str, Any]):
            """Clear all voice samples for a speaker (keeps the person + their conversations).
            The speaker disappears from recognition until re-enrolled."""
            speaker_id = payload.get("speaker_id")
            rows = self.db_execute_sync("SELECT name FROM speakers WHERE id = ?", (speaker_id,))
            if not rows:
                raise HTTPException(status_code=404, detail=f"No speaker with id {speaker_id}")
            name = rows[0]["name"]
            speaker_dir = self._safe_speaker_dir(name)
            if speaker_dir is None:
                self.logger.warning(f"reset_voice: unsafe stored name {name!r} — no files touched")
            else:
                if os.path.isdir(speaker_dir):
                    for old in Path(speaker_dir).glob("*.wav"):
                        try:
                            old.unlink()
                        except OSError:
                            pass
                if self.speaker_system is not None and self.speaker_system_ready:
                    await asyncio.to_thread(self.speaker_system.rebuild_speaker, name)
                    self._current_status["speaker_count"] = len(self.speaker_system.speaker_names)
            self.logger.info(f"Voice reset for '{name}' — all samples deleted")
            self.send_message_to_frontend({"type": "speakerid_speakers_changed"})
            return {"name": name, "reset": True}

        @self.router.post("/records")
        async def attach_record(payload: Dict[str, Any]):
            recorder_id = payload.get("recorder_id")
            speakers_id = payload.get("speakers_id")
            if recorder_id is None or speakers_id is None:
                raise HTTPException(status_code=400, detail="recorder_id and speakers_id are required")
            # Ints by contract (they feed DB lookups and the enrolled WAV filename) —
            # a string id would only fail later at the lookup, so reject it here.
            if not isinstance(recorder_id, int) or not isinstance(speakers_id, int):
                raise HTTPException(status_code=400, detail="recorder_id and speakers_id must be integers")

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
                speaker_dir = self._safe_speaker_dir(speaker_name)
                if speaker_dir is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Speaker name {speaker_name!r} is not safe to use as a folder",
                    )
                os.makedirs(speaker_dir, exist_ok=True)
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
                    warning = "Speaker system not ready; WAV saved, will enroll when the speaker system loads"
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

        @self.router.post("/process_audio_chunk")
        async def process_audio_chunk_endpoint(audio_file: UploadFile = File(...), sample_rate: Optional[int] = Form(None)):
            """Receive audio chunk for real-time speaker identification"""
            # Privacy gate: accept no mic audio (and write no debug chunk) when disabled.
            if not self.voice_profiles_enabled:
                raise HTTPException(status_code=403, detail="Voice profiles are disabled")
            try:
                # Read audio data from uploaded file
                audio_bytes = await audio_file.read()

                # sample_rate is a multipart FORM field (that's what the frontend
                # sends) — without Form() FastAPI would look for a query parameter
                # and silently ignore the value the client actually sent.
                effective_sample_rate = sample_rate if sample_rate is not None else 48000

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
                        # Process chunk using the existing hook method logic — off the
                        # event loop: the ECAPA forward pass must not block the server.
                        result = await asyncio.to_thread(self.process_audio_chunk, pcm_data, 16000)
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
                    # WAV upload: parse the RIFF header for the real sample rate (the
                    # form value stays a fallback) and feed only the PCM payload to the
                    # buffer — header bytes are not audio samples.
                    pcm_bytes, wav_rate = self._parse_wav_pcm(audio_bytes, sample_rate)
                    if wav_rate is not None:
                        effective_sample_rate = wav_rate
                    result = await asyncio.to_thread(self.process_audio_chunk, pcm_bytes, effective_sample_rate)
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
        - confidence_threshold_high (0.51): the COMMIT bar. Once a speaker is the
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
        """Inject the speaker into the LLM context + topbar. The LOCK (which freezes
        detection for the rest of the conversation) only applies when a conversation is
        active — during the inter-conversation gap the same injection is a continuous
        PRE-WARM: it keeps the prompt ready but stays unlocked so the ambient speaker
        can be revised (every re-detection refreshes the prewarm_ttl clock). A
        conversation-scoped commit (or a manual set_speaker) is what actually locks."""
        status = "confirmed" if self.conversation_active else "prewarmed"
        if self.conversation_active:
            self.committed_speaker = name          # LOCK — conversations only
        else:
            self._last_prewarm_refresh = time.time()   # pre-warm: refresh the TTL
        self.last_speaker.id = name
        self.last_speaker.confidence = score
        self.last_phrase_speaker.id = name
        self.last_phrase_speaker.confidence = score
        self.is_processing = False
        self.logger.info(
            f"Speaker {status.upper()}: {name} (score {score:.2f})"
            + (" — detection locked for this conversation" if self.conversation_active
               else " — pre-warm (unlocked)")
        )
        # _update_speaker_context updates context_manager["speaker_info"] AND pushes
        # the speaker to the frontend in one message (status = confirmed|prewarmed).
        self._update_speaker_context(name, score, status, method="auto")

    def _send_tentative(self, name, score):
        """Show a tentative (unconfirmed) candidate in the topbar WITHOUT injecting a
        name into the LLM context. name=None ⇒ unknown/listening. Identical consecutive
        pushes (same name+status) are deduplicated — this fires every cooldown while
        nobody recognizable is talking."""
        self.last_speaker.id = name
        self.last_speaker.confidence = score
        push_key = (name or "unknown", "partial" if name else "unknown")
        if push_key == self._last_tentative_push:
            return
        self._last_tentative_push = push_key
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
        name. Collapse whitespace; strip filesystem-illegal chars, control chars, and
        leading/trailing dots/spaces (Win32 silently strips trailing dots/spaces at
        folder creation, which would desync the DB name from the on-disk folder).
        Return '' (→ rejected by callers) for empty input, Windows-reserved device
        names (CON, COM1, … — reserved with any extension too), and names over
        MAX_NAME_LEN chars.
        """
        if raw is None:
            return ""
        name = str(raw).strip()
        name = re.sub(r"\s+", " ", name)               # collapse internal whitespace
        name = re.sub(r"[\x00-\x1f\x7f]", "", name)    # control chars — illegal in Windows filenames
        name = re.sub(r'[\\/:\*\?"<>\|]', "", name)    # filesystem-illegal / path separators
        name = name.strip(". ")                        # no hidden files / ../ tricks / Win32 dot-stripping
        stem = name.split(".", 1)[0].strip()           # reserved names stay reserved with an extension
        if len(name) > self.MAX_NAME_LEN or stem.upper() in self.RESERVED_NAMES:
            return ""
        return name

    def _safe_speaker_dir(self, name) -> Optional[str]:
        """On-disk path for a speaker's voices/<name>/ folder, for every endpoint that
        touches files (list/delete/reset/enroll). Re-sanitizes the DB value and
        verifies the resolved path sits directly inside voices/: realpath also
        resolves symlinks/junctions, so a crafted or corrupt data import can't
        redirect a delete or an enrollment outside voices/. Returns None when the
        name can't be used safely; callers skip the file work and log/4xx.
        """
        clean = self._sanitize_name(name)
        if not clean:
            return None
        voices_dir = os.path.realpath(os.path.join(self.plugin_folder, "voices"))
        speaker_dir = os.path.realpath(os.path.join(voices_dir, clean))
        if os.path.dirname(speaker_dir) != voices_dir:
            return None
        return speaker_dir

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
    
    @staticmethod
    def _parse_wav_pcm(data: bytes, sample_rate_hint: Optional[int]):
        """Split a WAV blob into (pcm_bytes, sample_rate). Walks the RIFF chunks so
        extended headers (LIST/etc.) don't leak non-audio bytes into the buffer.
        Non-WAV input is returned unchanged with the hint (assumed raw PCM)."""
        if len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            try:
                rate = None
                pos = 12
                while pos + 8 <= len(data):
                    chunk_id = data[pos:pos + 4]
                    chunk_size = int.from_bytes(data[pos + 4:pos + 8], "little")
                    body = pos + 8
                    if chunk_id == b"fmt " and chunk_size >= 16:
                        rate = int.from_bytes(data[body + 4:body + 8], "little")
                    elif chunk_id == b"data":
                        return data[body:body + chunk_size], rate or sample_rate_hint
                    pos = body + chunk_size + (chunk_size & 1)  # chunks are word-aligned
            except Exception:
                pass
        return data, sample_rate_hint

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

