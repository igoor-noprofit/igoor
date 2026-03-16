from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import threading
import json,os, requests,time
import asyncio
import pyaudio
import wave
import groq
import numpy as np
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils import setup_logger, get_base_language_code
from pathlib import Path

WAKEWORD_MODELS_DIR = os.path.join(os.path.dirname(__file__), "static", "wakeword")
CUSTOM_WAKEWORD_DIR = "custom_wakeword"

class WakewordDetector:
    def __init__(self, model_path: str, sensitivity: float = 0.5, logger=None):
        self.model_path = model_path
        self.sensitivity = sensitivity
        self.logger = logger
        self.model = None
        self.is_loaded = False
        self.audio_buffer = np.array([], dtype=np.int16)  # openWakeWord requires int16
        self.sample_rate = 16000
        self.chunk_size = 1280  # 80ms at 16kHz
        
    def load_model(self):
        try:
            from openwakeword import Model as OpenWakeWordModel
            if self.logger:
                self.logger.info(f"Loading wakeword model from: {self.model_path}")

            # Load custom wakeword model
            self.model = OpenWakeWordModel(wakeword_models=[self.model_path])

            self.is_loaded = True
            if self.logger:
                self.logger.info(f"Wakeword model loaded successfully: {self.model_path}")
            return True
        except ImportError as e:
            if self.logger:
                self.logger.error(f"openwakeword not installed: {e}")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error loading wakeword model: {e}")
            return False
    
    def process_chunk(self, audio_data: bytes) -> bool:
        if not self.is_loaded or self.model is None:
            return False
        try:
            audio_np = np.frombuffer(audio_data, dtype=np.int16)  # Keep as int16 for openWakeWord

            # Debug: check audio level (convert to float for RMS calculation)
            audio_float = audio_np.astype(np.float32) / 32768.0
            audio_rms = np.sqrt(np.mean(audio_float ** 2))
            audio_max = np.max(np.abs(audio_float))

            self.audio_buffer = np.concatenate([self.audio_buffer, audio_np])
            if len(self.audio_buffer) >= self.chunk_size:
                chunk_to_process = self.audio_buffer[:self.chunk_size]
                self.audio_buffer = self.audio_buffer[self.chunk_size:]
                prediction = self.model.predict(chunk_to_process)

                # Debug: log prediction scores every 10 chunks OR when audio is detected
                if not hasattr(self, '_prediction_count'):
                    self._prediction_count = 0
                    # Log available models once
                    if self.logger:
                        self.logger.info(f"Available models: {list(self.model.models.keys())}")
                self._prediction_count += 1

                # Log every 5 chunks for debugging
                if self._prediction_count % 5 == 0 and self.logger:
                    all_scores = ", ".join([f"{k}: {v:.4f}" for k, v in prediction.items()])
                    print(f"Wakeword #{self._prediction_count}: {all_scores} | RMS: {audio_rms:.4f}, Max: {audio_max:.4f}")

                # Check all models for detection
                for model_name, score in prediction.items():
                    if score > 0.01 and self.logger:
                        print(f"Score spike: {model_name} = {score:.4f}")
                    if score >= self.sensitivity:
                        if self.logger:
                            print(f"Wakeword DETECTED! {model_name} = {score:.4f}")
                        return True
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error processing wakeword chunk: {e}")
            return False
    
    def set_sensitivity(self, sensitivity: float):
        self.sensitivity = max(0.1, min(0.9, sensitivity))
        
    def destroy(self):
        self.model = None
        self.is_loaded = False
        self.audio_buffer = np.array([], dtype=np.int16)

class Asrjs(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.is_paused = False
        self.recording = False  # Initialize recording state
        self.is_loaded = False  # Make sure this is initialized
        self.wakeword_detected = False  # Initialize wakeword state
        self.wakeword_model_loaded = False  # Track wakeword model loading
        super().__init__(plugin_name, pm)
        
        # Create recordings directory for persistent audio files
        recordings_dir = os.path.join(self.plugin_folder, "recordings")
        if not os.path.exists(recordings_dir):
            os.makedirs(recordings_dir, exist_ok=True)
            self.logger.info(f"Created recordings directory: {recordings_dir}")
        else:
            # Clean up old recordings on startup
            try:
                for filename in os.listdir(recordings_dir):
                    file_path = os.path.join(recordings_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                self.logger.info(f"Cleaned up old recordings from: {recordings_dir}")
            except Exception as e:
                self.logger.error(f"Error cleaning up recordings: {e}")
        
        # Set up audio parameters
        self.sample_rate = 16000
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.chunk_size = 4000
        
        # Set up temporary file for audio storage (WebM format)
        self.temp_audio_file = os.path.join(self.plugin_folder, "temp_audio.webm")
        
        # Wakeword detector initialization
        self.wakeword_detector = None
        self.wakeword_enabled = False
        self.wakeword_sensitivity = 0.5
        
        self._setup_custom_wakeword_dir()

        # Pre-download openwakeword models (melspectrogram, etc.) if openwakeword is installed
        # download_models() checks if files exist before downloading - safe to call every init
        try:
            from openwakeword.utils import download_models
            self.logger.info("Checking openwakeword models...")
            download_models()
        except ImportError:
            self.logger.debug("openwakeword not installed, skipping model download")
        except Exception as e:
            self.logger.warning(f"Could not download openwakeword models: {e}")
        
    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        
        # Get global language preference and process it
        self.lang_code = get_base_language_code(self.lang, default_lang="fr") # Default to 'fr' if not found or empty
        
        self.wakeword = self.settings.get("wakeword")
        
        self.continuous = self.settings.get("continuous", False) # Ensure default for continuous
        self.conversation_abandoned = False  # Track if conversation was abandoned
        print (f"ASRJS settings: {self.settings}, Global Lang for ASR: {self.lang_code}")
        
        self.wakeword_enabled = self.settings.get("wakeword_enabled", False)
        self.wakeword_sensitivity = self.settings.get("wakeword_sensitivity", 0.5)
        
        # Load wakeword model if enabled and continuous mode
        if self.continuous and self.wakeword_enabled:
            self._load_wakeword_model()
        
        self.model_provider = self.settings.get("model_provider", "groq")  # Default to Groq if not set
        if self.model_provider not in self.settings.get("allowed_model_providers", []):
            self.logger.error(f"Model provider '{self.model_provider}' is not allowed. Defaulting to groq")
            self.model_provider = "groq"
            print("Model provider not found, using default model provider: Groq")
        
        self.model_thread = threading.Thread(target=self.load_model, daemon=True)
        self.model_thread.start()
        print("Started loading model in background.")
        
        monitor_thread = threading.Thread(target=self.run_monitor_loading, daemon=True)
        monitor_thread.start()
        
        # Initialize FastAPI router
        self.router: Optional[APIRouter] = None
        self._ensure_router()
        
        # Register router with FastAPI app
        fastapi_app = getattr(self.pm, "fastapi_app", None)
        if fastapi_app and not getattr(self, "_router_registered", False):
            fastapi_app.include_router(self.router)
            self._router_registered = True
        elif fastapi_app is None:
            self.logger.warning("FastAPI app not available; asrjs endpoints not registered")
    
    @hookimpl
    async def restart_asr(self):
        print(f"ASRJS restart_asr called: continuous={self.continuous}, conversation_abandoned={self.conversation_abandoned}, is_paused={self.is_paused}")
        if (self.continuous):
            # Don't resume listening if conversation was abandoned
            if self.conversation_abandoned:
                new_status = "ready"
            else:
                self.is_paused = False
                self.wakeword_detected = True
                new_status = "listening"  # VAD handles speech detection
        else:
            new_status="listening"
        print(f"ASRJS restart_asr sending status: {new_status}")
        await self.send_status(new_status)
    
    def run_monitor_loading(self):
        asyncio.run(self.monitor_loading())

    async def monitor_loading(self):
        # Wait for ASR model to load
        while not self.is_loaded:
            await asyncio.sleep(1)

        # If wakeword is enabled, also wait for wakeword model
        if self.continuous and self.wakeword_enabled:
            self.logger.info("Waiting for wakeword model to load...")
            while not self.wakeword_model_loaded:
                await asyncio.sleep(0.5)
                # Timeout after 30 seconds
                if hasattr(self, '_wakeword_wait_start'):
                    if asyncio.get_event_loop().time() - self._wakeword_wait_start > 30:
                        self.logger.error("Timeout waiting for wakeword model")
                        break
                else:
                    self._wakeword_wait_start = asyncio.get_event_loop().time()

        # Check if wakeword was required but failed to load
        if self.continuous and self.wakeword_enabled and not self.wakeword_model_loaded:
            self.logger.error("Wakeword model required but failed to load. Plugin will not be ready.")
            await self.send_status("error")
            return

        print("Model is ready to use.")
        await self.send_status("ready")
        self.send_settings_to_frontend()
        # await self.test_wake_word()
    
    def load_model(self):
        if (self.model_provider == "groq"):
            """Initialize the Groq client for Whisper transcription"""
            try:
                # Attempt to get AI settings from onboarding plugin
                # Correctly fetch the 'ai' settings from the 'onboarding' plugin's root
                onboarding_ai_settings = self.settings_manager.get_nested(["plugins", "onboarding", "ai"])
                self.logger.info(f"Onboarding AI settings found: {onboarding_ai_settings}") # Corrected f-string
                api_key_to_use = None
                
                if onboarding_ai_settings and \
                    onboarding_ai_settings.get("provider") == "groq" and \
                    onboarding_ai_settings.get("api_key"):
                    api_key_to_use = onboarding_ai_settings.get("api_key")
                    self.logger.info("Using Groq API key from global AI settings (onboarding).")
                else:
                    # Fallback to plugin's own settings
                    api_key_to_use = self.settings.get("api_key")
                    if api_key_to_use:
                        self.logger.info("Using Groq API key from asrwhisper plugin settings.")
                    else:
                        self.logger.error("No Groq API key found in global AI settings or asrwhisper plugin settings.")
                        self.is_loaded = False # Ensure is_loaded is false if API key is missing
                        return

                if not api_key_to_use: # Double check if api_key_to_use ended up being None or empty
                    self.logger.error("No Groq API key could be determined.")
                    self.is_loaded = False
                    return
                    
                # Initialize Groq client
                self.client = groq.Groq(api_key=api_key_to_use)
                # Get model name from settings, default to whisper-large-v3
                self.model = self.settings.get("model_name", "whisper-large-v3")
                
                # Mark as loaded
                self.is_loaded = True
                # Don't call mark_ready() here - let the check at end of function handle it
                # Removed: asyncio.create_task(self.send_status("ready"))
                # This was causing the "no running event loop" error and is redundant
                # as monitor_loading handles sending the "ready" status.
                self.logger.info(f"Groq Whisper initialized successfully with model: {self.model}")
            except ImportError as e:
                self.logger.error(f"Failed to import required modules: {e}")
                self.is_loaded = False
                # raise # Optionally re-raise if it's critical
            except Exception as e:
                self.logger.error(f"Error initializing Groq client: {e}")
                self.is_loaded = False
                # raise # Optionally re-raise
        elif (self.model_provider == "mistral"):
            self.model=self.settings.get("model_name", "voxtral-mini-latest")

        self.is_loaded = True
        # Only mark ready if wakeword isn't required, or if it loaded successfully
        if not (self.continuous and self.wakeword_enabled) or self.wakeword_model_loaded:
            self.mark_ready()
    
    async def handle_wake_word(self,following_text):
        # Guard against empty transcriptions
        if not following_text or not following_text.strip():
            print("Empty transcription, ignoring")
            return
        print(f"Wake word detected! Text: '{following_text}'")
        await self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=following_text, author="def",msg_input="asrwhisper")
        await self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + following_text)

    async def process_incoming_message(self, message):
        """Extend the base plugin's message handler with ASR-specific actions"""
        try:
            data = json.loads(message)
            if 'action' in data:
                # Handle ASR-specific actions
                if data['action'] == 'set_continuous_mode':
                    self.continuous = data.get('continuous', False)
                    self.update_my_settings("continuous", self.continuous)
                    # Create the task properly with asyncio
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.restart_with_new_mode())
                elif not self.continuous:
                    if data['action'] == 'start_recording':
                        self.recording = True
                        asyncio.create_task(self.send_status("recording"))
                    elif data['action'] == 'stop_recording':
                        self.recording = False
                        asyncio.create_task(self.send_status("listening"))
                    elif data['action'] == 'trigger_hook':
                        # Handle hook triggers from frontend
                        hook_name = data.get('hook_name')
                        if hook_name == 'transcribing_started':
                            # Send "transcribing_started" status so conversation component can show typing indicator
                            asyncio.create_task(self.send_status("transcribing_started"))
                            # Trigger to other plugins if needed
                            await self.pm.trigger_hook(hook_name="transcribing_started")
                        else:
                            self.logger.warning(f"Unknown hook trigger: {hook_name}")
                    elif data['action'] == 'process_audio_chunk':
                        # Handle audio chunks from frontend for speaker identification
                        audio_data = data.get('audio_data')
                        if audio_data:
                            await self.pm.trigger_hook(
                                hook_name="process_audio_chunk", 
                                audio_data=audio_data.encode('utf-8') if isinstance(audio_data, str) else audio_data,
                                sample_rate=16000
                            )
                    elif data['action'] == 'transcribe_audio':
                        # Handle complete audio file for transcription
                        audio_base64 = data.get('audio')
                        if audio_base64:
                            import base64
                            # Decode base64 to binary
                            audio_bytes = base64.b64decode(audio_base64)
                            
                            # Save to temp file as WebM (native browser format)
                            temp_file_path = os.path.join(self.plugin_folder, f"temp_upload_{int(time.time())}.webm")
                            
                            with open(temp_file_path, 'wb') as f:
                                f.write(audio_bytes)
                            
                            # Update temp_audio_file path for existing transcription logic
                            original_temp_file = self.temp_audio_file
                            self.temp_audio_file = temp_file_path
                            
                            # Transcribe audio
                            text = await self.transcribe_audio()
                            
                            # Restore original temp file path
                            self.temp_audio_file = original_temp_file
                            
                            # Clean up uploaded file
                            try:
                                os.remove(temp_file_path)
                            except:
                                pass
                            
                            if text:
                                text = self.clean_whisper_silence(text)
                                # Handle transcription result
                                await self.handle_wake_word(text)
                            
                            # Send result back to frontend
                            await self.send_message_to_frontend({
                                "type": "transcription_result",
                                "text": text
                            })
                else:
                    # If not an ASR-specific action, let the base plugin handle it
                    super().process_incoming_message(message)
        except json.JSONDecodeError:
            print("Received invalid JSON message")

    async def restart_with_new_mode(self):
        """Restart ASR with the new mode settings"""
        try:
            # Stop current processing
            # Stream is now handled by frontend, no cleanup needed
            # if hasattr(self, 'stream') and self.stream:
            #     self.stream.stop_stream()
            #     self.stream.close()
            if hasattr(self, 'p') and self.p:
                self.p.terminate()
            
            # Reset states
            self.is_paused = False
            self.recording = False
            self.wakeword_detected = False
            
            # Send status update before restarting
            await self.send_status("ready")
            
            # Restart with new mode
            # No need to start stream, we'll use HTTP endpoints
        except Exception as e:
            print(f"Error during ASR restart: {e}")
            await self.send_status("error")
    
    
    async def test_wake_word(self):
        await self.handle_wake_word("est-ce que tu aimes le gateau de riz?")

    def save_audio_to_file(self, audio_buffer):
        """Save the audio buffer to a WAV file"""
        try:
            import wave
            
            wf = wave.open(self.temp_audio_file, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.p.get_sample_size(self.audio_format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(audio_buffer))
            wf.close()
            return True
        except Exception as e:
            self.logger.error(f"Error saving audio to file: {e}")
            return False
            
    async def transcribe_audio(self):
        """Transcribe audio using Groq Whisper"""
        try:
            if not os.path.exists(self.temp_audio_file):
                return ""
                
            # Check file size to avoid sending empty files
            if os.path.getsize(self.temp_audio_file) < 1000:  # Less than 1KB
                return ""
                
            # Use asyncio to run the transcription in a separate thread
            loop = asyncio.get_running_loop()
            if (self.model_provider == "groq"):
                result = await loop.run_in_executor(None, self._transcribe_with_groq)
            elif (self.model_provider == "mistral"):
                result = await loop.run_in_executor(None, self._transcribe_with_voxtral)
            return result
        except Exception as e:
            self.logger.error(f"Error transcribing audio: {e}")
            return ""

    def _transcribe_with_voxtral(self):
        """Helper method to run Voxtral transcription in a separate thread"""
        try:
            url = "https://api.mistral.ai/v1/audio/transcriptions"
            api_key = self.settings.get("voxtral_api_key", "")
            if not api_key:
                self.logger.error("No Voxtral API key provided.")
                return ""
            headers = {
                "x-api-key": api_key
            }
            print (f"Transcribing with Voxtral using model: {self.model}, language: {self.lang_code}")
            files = {
                "file": open(self.temp_audio_file, "rb"),
                "model": (None, self.model),
                "language": (None, self.lang_code)
            }
            response = requests.post(url, headers=headers, files=files)
            if response.status_code == 200:
                data = response.json()
                return data.get("text", "")
            else:
                self.logger.error(f"Voxtral API error: {response.status_code} {response.text}")
                return ""
        except Exception as e:
            self.logger.error(f"Voxtral transcription error: {e}")
            return ""
            
    def _transcribe_with_groq(self):
        """Helper method to run Groq transcription in a separate thread"""
        try:
            with open(self.temp_audio_file, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model,
                    language=self.lang_code  # Use the processed global language
                )
                return transcription.text
        except Exception as e:
            self.logger.error(f"Groq transcription error: {e}")
            return ""
    
    def _setup_custom_wakeword_dir(self):
        """Set up custom wakeword directory in APPDATA"""
        try:
            custom_dir = os.path.join(self.plugin_folder, CUSTOM_WAKEWORD_DIR)
            if not os.path.exists(custom_dir):
                os.makedirs(custom_dir, exist_ok=True)
                self.logger.info(f"Created custom wakeword directory: {custom_dir}")
            self.custom_wakeword_dir = custom_dir
        except Exception as e:
            self.logger.error(f"Error setting up custom wakeword directory: {e}")
            self.custom_wakeword_dir = None
    
    def _get_default_wakeword_model_path(self):
        """Get the default wakeword model path based on language locale"""
        # Use full locale for model naming: locales/fr_FR/hey_igoor_fr_FR.onnx
        locale = self.lang  # e.g., "fr_FR" or "en_EN"
        model_name = f"hey_igoor_{locale}.onnx"

        # Build path in locales folder
        locales_dir = os.path.join(os.path.dirname(__file__), "locales", locale)
        model_path = os.path.join(locales_dir, model_name)

        if os.path.exists(model_path):
            return model_path
        else:
            self.logger.warning(f"Default wakeword model not found: {model_path}")
            return None
    
    def _get_custom_wakeword_model_path(self):
        """Get the custom wakeword model path from settings.

        wakeword_model can be:
        - "" or "default" → use default model for language
        - "filename.onnx" → use custom model from custom_wakeword directory
        """
        wakeword_model = self.settings.get("wakeword_model", "")

        # Empty or "default" means use default model
        if not wakeword_model or wakeword_model == "default":
            self.logger.info("No custom wakeword model set, using default")
            return None

        # Construct full path from filename
        full_path = os.path.join(self.custom_wakeword_dir, wakeword_model)
        self.logger.info(f"Checking custom wakeword path: {full_path}")

        if os.path.exists(full_path):
            self.logger.info(f"Custom wakeword model found: {full_path}")
            return full_path

        self.logger.warning(f"Custom wakeword file not found: {full_path}")
        return None
    
    def _load_wakeword_model(self):
        """Load the wakeword detection model.

        wakeword_model can be:
        - "" or "default" → use default model for language
        - "filename.onnx" → use custom model from custom_wakeword directory
        """
        if not self.wakeword_enabled or not self.continuous:
            self.logger.info("Wakeword not enabled or not in continuous mode, skipping model load")
            return False

        # Try custom model first, fall back to default
        model_path = self._get_custom_wakeword_model_path()
        if not model_path:
            model_path = self._get_default_wakeword_model_path()
            self.logger.info(f"Using default wakeword model path: {model_path}")

        if not model_path:
            self.logger.error("No wakeword model available")
            return False

        # Destroy existing detector if any
        if self.wakeword_detector:
            self.wakeword_detector.destroy()

        # Create new detector
        self.wakeword_detector = WakewordDetector(
            model_path=model_path,
            sensitivity=self.wakeword_sensitivity,
            logger=self.logger
        )

        # Load the model
        success = self.wakeword_detector.load_model()
        if success:
            self.logger.info(f"Wakeword model loaded successfully from: {model_path}")
        else:
            self.logger.error(f"Failed to load wakeword model from: {model_path}")

        return success

    def _ensure_router(self):
        if self.router:
            return

        self.router = APIRouter(prefix="/api/plugins/asrjs", tags=["asrjs"])
        
        @self.router.post("/start_recording")
        async def start_recording_endpoint():
            """Start recording via HTTP endpoint"""
            try:
                # Reset abandonment flag when user clicks to start new conversation
                self.conversation_abandoned = False
                
                await self.send_status("recording")
                await self.pm.trigger_hook(hook_name="transcribing_started")
                return {"status": "started"}
            except Exception as e:
                self.logger.error(f"Error starting recording: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/stop_recording")
        async def stop_recording_endpoint():
            """Stop recording via HTTP endpoint"""
            try:
                await self.send_status("listening")
                return {"status": "stopped"}
            except Exception as e:
                self.logger.error(f"Error stopping recording: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/transcribe")
        async def transcribe_endpoint(audio_file: UploadFile = File(...)):
            """Receive complete audio file for transcription"""
            try:
                # Save uploaded file with timestamp - now supporting WAV format
                timestamp = int(time.time())
                
                # Determine file extension based on content type
                if audio_file.content_type and 'wav' in audio_file.content_type:
                    file_ext = 'wav'
                else:
                    file_ext = 'webm'  # Fallback to WebM for compatibility
                
                temp_file_path = os.path.join(self.plugin_folder, f"recordings/recording_{timestamp}.{file_ext}")
                
                with open(temp_file_path, 'wb') as f:
                    content = await audio_file.read()
                    f.write(content)
                
                # Use existing transcription methods
                # Update temp_audio_file path for existing transcription logic
                original_temp_file = self.temp_audio_file
                self.temp_audio_file = temp_file_path
                
                # Transcribe the audio
                await self.pm.trigger_hook(hook_name="transcribing_started")
                text = await self.transcribe_audio()
                
                # Restore original temp file path
                self.temp_audio_file = original_temp_file
                
                # Audio file persists in recordings folder, no cleanup needed
                # try:
                #     os.remove(temp_file_path)
                # except:
                #     pass
                
                
                if text:
                    text = self.clean_whisper_silence(text)
                    # Handle transcription result
                    await self.handle_wake_word(text)
                await self.pm.trigger_hook(hook_name="transcribing_ended")
                
                # Reset status to "listening" for continuous mode after transcription completes
                # But only if conversation wasn't abandoned
                if self.continuous and not self.conversation_abandoned:
                    await self.send_status("listening")
                
                return {"status": "success", "text": text}
                
            except Exception as e:
                self.logger.error(f"Error transcribing audio: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Wakeword detection endpoints
        @self.router.post("/wakeword_chunk")
        async def wakeword_chunk_endpoint(audio_chunk: UploadFile = File(...)):
            """Receive audio chunk for wakeword detection"""
            try:
                if not self.wakeword_detector or not self.wakeword_enabled:
                    return {"error": "Wakeword detection not enabled"}

                # Read audio chunk - frontend sends raw Int16 PCM data (not WAV)
                chunk_data = audio_chunk.file.read()

                # Check if this looks like a WAV file (starts with "RIFF")
                if chunk_data[:4] == b'RIFF' and len(chunk_data) > 44:
                    raw_pcm_data = chunk_data[44:]  # Strip WAV header
                else:
                    raw_pcm_data = chunk_data  # Raw Int16 data, no header

                # Debug log every 10 chunks
                if not hasattr(self, '_wakeword_chunk_count'):
                    self._wakeword_chunk_count = 0
                self._wakeword_chunk_count += 1
                if self._wakeword_chunk_count % 10 == 0:
                    self.logger.info(f"Wakeword chunk #{self._wakeword_chunk_count}, size: {len(raw_pcm_data)} bytes")

                detected = self.wakeword_detector.process_chunk(raw_pcm_data)
                if detected:
                    self.logger.info("WAKEWORD DETECTED! Notifying frontend...")
                    # Notify frontend to start VAD and resume listening
                    self.send_message_to_frontend({
                        "action": "wakeword_detected"
                    })
                    return {"status": "success", "detected": True}

                return {"status": "success", "detected": False}

            except Exception as e:
                self.logger.error(f"Error processing wakeword chunk: {e}")
                return {"error": str(e)}

        @self.router.post("/upload_wakeword_model")
        async def upload_wakeword_model(file: UploadFile = File(...)):
            """Upload custom wakeword model"""
            try:
                # Check custom directory exists
                if not self.custom_wakeword_dir:
                    return {"status": "error", "message": "Custom wakeword directory not available"}

                # Save file
                filename = file.filename or "custom_model.onnx"
                file_path = os.path.join(self.custom_wakeword_dir, filename)

                contents = await file.read()
                with open(file_path, "wb") as f:
                    f.write(contents)

                # Update settings: store only the filename in wakeword_model
                self.settings["wakeword_model"] = filename
                self.update_my_settings("wakeword_model", filename)

                # Reload the wakeword model
                self._load_wakeword_model()

                self.logger.info(f"Custom wakeword model saved to: {file_path} and loaded")
                return {"status": "success", "path": file_path, "filename": filename}

            except Exception as e:
                self.logger.error(f"Error uploading wakeword model: {e}")
                return {"status": "error", "message": str(e)}

        @self.router.get("/list_custom_wakeword_models")
        async def list_custom_wakeword_models():
            """List all custom wakeword models in the custom directory"""
            try:
                if not self.custom_wakeword_dir or not os.path.exists(self.custom_wakeword_dir):
                    return {"models": []}

                models = []
                for f in os.listdir(self.custom_wakeword_dir):
                    if f.endswith('.onnx'):
                        models.append(f)

                return {"models": models}

            except Exception as e:
                self.logger.error(f"Error listing custom wakeword models: {e}")
                return {"models": [], "error": str(e)}

        @self.router.delete("/delete_custom_wakeword_model/{filename}")
        async def delete_custom_wakeword_model(filename: str):
            """Delete a custom wakeword model"""
            try:
                if not self.custom_wakeword_dir:
                    return {"status": "error", "message": "Custom directory not available"}

                file_path = os.path.join(self.custom_wakeword_dir, filename)
                if not os.path.exists(file_path):
                    return {"status": "error", "message": "Model not found"}

                os.remove(file_path)

                # If this was the currently selected model, reset to default
                if self.settings.get("wakeword_model") == filename:
                    self.settings["wakeword_model"] = ""
                    self.update_my_settings("wakeword_model", "")
                    # Reload with default model
                    self._load_wakeword_model()

                self.logger.info(f"Deleted custom wakeword model: {filename}")
                return {"status": "success"}

            except Exception as e:
                self.logger.error(f"Error deleting custom wakeword model: {e}")
                return {"status": "error", "message": str(e)}

    def clean_whisper_silence(self, text):
        print(f"Transcribed text: {text}")
        SILENCE_STRINGS = [
            "Sous-titrage ST' 501",
            "Sous-titrage Société Radio-Canada"
        ]
        for s in SILENCE_STRINGS:
            # Remove at start
            if text.strip().startswith(s):
                text = text.strip()[len(s):].strip()
            # Remove at end
            if text.strip().endswith(s):
                text = text.strip()[:-len(s)].strip()
            print(f"Cleaned text: {text}")
        
        text = text.replace('\u200b', '')
        text = text.replace('\ufeff', '')
        text = text.replace('\u00a0', ' ')
        
        if text == "." or text == " ." or not text:
            return ""
        return text
        
        
    @hookimpl
    async def add_msg_to_conversation(self, msg, author, msg_input):
        """Ensure flags are set so restart_asr will resume VAD after TTS finishes"""
        if self.continuous:
            self.conversation_abandoned = False
            self.wakeword_detected = True
            print(f"ASRJS add_msg_to_conversation: set conversation_abandoned=False, wakeword_detected=True")

    @hookimpl
    async def pause_asr(self):
        self.is_paused = True
        await(self.send_status("paused"))
        
    @hookimpl
    async def abandon_conversation(self, cause="timeout"):
        try:
            print("ASRJS received ABANDON_CONVERSATION trigger")
            # Reset wake word detection
            self.wakeword_detected = False
            
            # Mark conversation as abandoned to prevent status reset after transcription
            self.conversation_abandoned = True
            
            # If continuous mode is active, pause VAD to stop listening
            if self.continuous:
                print("ASRJS: Continuous mode is active, pausing VAD")
                await self.send_status("ready")  # Send "ready" status instead of "listening"
            else:
                print("ASRJS: Non-continuous mode, sending listening status")
                await self.send_status("listening")
                
            print("ASRJS after_conversation_end completed successfully")
        except Exception as e:
            print(f"Error in ASRJS after_conversation_end: {e}")
    
    '''
    To support external wakeword mechanism
    '''
    @hookimpl
    def wakeword_detected(self):
        self.wakeword_detected = True

    @hookimpl
    def get_asrjs_config(self):
        """Provide asrjs configuration to other plugins"""
        return self.settings
        
        
    @hookimpl
    async def change_view(self,lastview,currentview):
        print("CHANGE VIEW IN ASRJS")
        if not self.is_paused:
            if currentview == 'onboarding':
                await self.pause_asr()

    @hookimpl
    def global_settings_updated(self):
        """Called when global settings are updated - reload Groq client if API key changed."""
        self.logger.info("ASRJS: global_settings_updated - reloading Groq client")
        # Reload settings from disk
        self.settings = self.get_my_settings()
        # Reload model provider from settings
        self.model_provider = self.settings.get("model_provider", "groq")
        # Reinitialize the model/client with new settings
        self.load_model()
        # Send updated settings to frontend
        self.send_settings_to_frontend()