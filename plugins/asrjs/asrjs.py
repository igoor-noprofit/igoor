from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import threading
import json,os, requests,time
import asyncio
import pyaudio
import wave
import groq
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from utils import setup_logger, get_base_language_code

class Asrjs(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.is_paused = False
        self.recording = False  # Initialize recording state
        self.is_loaded = False  # Make sure this is initialized
        self.wakeword_detected = False  # Initialize wakeword state
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
        
    @hookimpl 
    def startup(self):
        self.settings = self.get_my_settings()
        
        # Get global language preference and process it
        self.lang_code = get_base_language_code(self.lang, default_lang="fr") # Default to 'fr' if not found or empty
        
        self.wakeword = self.settings.get("wakeword")
        
        self.continuous = self.settings.get("continuous", False) # Ensure default for continuous
        print (f"ASRJS settings: {self.settings}, Global Lang for ASR: {self.lang_code}")

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
    def restart_asr(self):
        if (self.continuous):
            self.is_paused = False
            self.wakeword_detected = True
            new_status="recording"
        else:
            new_status="listening"
            # Check if there's an existing event loop
        try:
            loop = asyncio.get_running_loop()
            # If there's a running loop, create a task
            loop.create_task(self.send_status(new_status))
        except RuntimeError:
            # If no running loop, use asyncio.run
            asyncio.run(self.send_status(new_status))
    
    def run_monitor_loading(self):
        asyncio.run(self.monitor_loading())

    async def monitor_loading(self):
        while not self.is_loaded:
            # Wait until the model is loaded
            time.sleep(1)
        self.model_thread.join()
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
            
        self.is_loaded=True
    
    async def handle_wake_word(self,following_text):
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
                            asyncio.create_task(self.send_status("transcribing"))
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
        
    def _ensure_router(self):
        """Initialize FastAPI router with transcription endpoint"""
        if self.router is not None:
            return
        
        self.router = APIRouter(prefix="/api/plugins/asrjs", tags=["asrjs"])
        
        @self.router.post("/start_recording")
        async def start_recording_endpoint():
            """Start recording via HTTP endpoint"""
            try:
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
                return {"status": "success", "text": text}
                
            except Exception as e:
                self.logger.error(f"Error transcribing audio: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def clean_whisper_silence(self, text):
        print(f"Transcribed text: {text}")
        """Remove known silence artifacts from Whisper output."""
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
        if text == "." or text == " ." or not text:
            return ""
        return text
        
        
    @hookimpl
    async def pause_asr(self):
        self.is_paused = True
        await(self.send_status("paused"))
        
    @hookimpl
    async def abandon_conversation(self, cause="timeout"):
        try:
            print("ASRJS received ABANDON_CONVERSATION trigger")
            # Your existing logic here
            self.wakeword_detected = False
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
    async def change_view(self,lastview,currentview):
        print("CHANGE VIEW IN ASRJS")
        if not self.is_paused:
            if currentview == 'onboarding':
                await self.pause_asr()