from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import threading
import json
import time
import asyncio
import os 
import pyaudio
import wave
import groq
from utils import setup_logger, get_base_language_code
import webrtcvad  

class Asrwhisper(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.is_paused = False
        self.recording = False  # Initialize recording state
        self.is_loaded = False  # Make sure this is initialized
        self.wakeword_detected = False  # Initialize wakeword state
        super().__init__(plugin_name, pm)
        self.vad = webrtcvad.Vad(2)  # 0-3, 3 is most aggressive, 2 is a good balance
        
    @hookimpl
    def startup(self):
        print ("ASRWHISPER IS STARTING UP")
        self.settings = self.get_my_settings()
        
        # Get global language preference and process it
        global_lang_full = self.settings_manager.get_nested(["plugins", "onboarding", "prefs", "lang"])
        self.lang = get_base_language_code(global_lang_full, default_lang="fr") # Default to 'fr' if not found or empty
        
        self.wakeword = self.settings.get("wakeword")
        self.continuous = self.settings.get("continuous", False) # Ensure default for continuous
        print (f"WHISPER settings: {self.settings}, Global Lang for ASR: {self.lang}")
        
        self.model_thread = threading.Thread(target=self.load_model, daemon=True)
        self.model_thread.start()
        print("Started loading model in background.")
        
        monitor_thread = threading.Thread(target=self.run_monitor_loading, daemon=True)
        monitor_thread.start()
    
    @hookimpl
    async def pause_asr(self):
        self.is_paused = True
        await(self.send_status("paused"))
        
    @hookimpl
    async def abandon_conversation(self, cause="timeout"):
        try:
            print("ASRWHISPER received ABANDON_CONVERSATION trigger")
            # Your existing logic here
            self.wakeword_detected = False
            await self.send_status("listening")
            print("ASRWHISPER after_conversation_end completed successfully")
        except Exception as e:
            print(f"Error in ASRWHISPER after_conversation_end: {e}")
    
    '''
    To support external wakeword mechanism
    '''
    @hookimpl
    def wakeword_detected(self):
        self.wakeword_detected = True
        
        
    @hookimpl
    async def change_view(self,lastview,currentview):
        print("CHANGE VIEW IN ASRWHISPER")
        if not self.is_paused:
            if currentview == 'onboarding':
                await self.pause_asr()
    
    @hookimpl
    def stop_asr(self):
        print("Stopping ASR")
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.start()
        self.send_message_to_frontend("listening")
        
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
    
    def start_stream(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
        self.stream.start_stream()
    
    def run_monitor_loading(self):
        asyncio.run(self.monitor_loading())

    async def monitor_loading(self):
        while not self.is_loaded:
            # Wait until the model is loaded
            time.sleep(1)
        self.model_thread.join()
        print("Model is ready to use.")
        await self.send_status("ready")
        await self.start()
        # await self.test_wake_word()
    
    def load_model(self):
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
            
            # Set up audio parameters
            self.sample_rate = 16000
            self.audio_format = pyaudio.paInt16
            self.channels = 1
            self.chunk_size = 4000
            
            # Set up temporary file for audio storage
            self.temp_audio_file = os.path.join(self.plugin_folder, "temp_audio.wav")
            
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
    
    async def handle_wake_word(self,following_text):
        print(f"Wake word detected! Text: '{following_text}'")
        await self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=following_text, author="def",msg_input="asrwhisper")
        await self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + following_text)

    async def start(self):
        if (self.continuous):
            self.wakeword_detected = False
            print("STARTING WAKEWORD RECOGNITION")
            await self.send_status("listening")
            # Initialize PyAudio and start the audio stream
            self.start_stream()
            
            # Create a buffer to store audio data
            audio_buffer = []
            silence_threshold = 500  # Adjust based on your environment
            silence_counter = 0
            recording = False
            
            try:
                while True:
                    if not self.is_paused:
                        data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                        if len(data) == 0:
                            break
                            
                        # Add data to buffer
                        audio_buffer.append(data)
                        
                        # Check if we should process the audio
                        if self.wakeword_detected or len(audio_buffer) * self.chunk_size / self.sample_rate > 5:  # Process every 5 seconds
                            # Convert buffer to WAV file
                            self.save_audio_to_file(audio_buffer)
                            
                            # Transcribe with Groq Whisper
                            text = await self.transcribe_audio()
                            
                            # Clear buffer after processing
                            audio_buffer = []
                            
                            if text:
                                print(f"Recognized text: {text}")
                                if self.wakeword_detected:
                                    await self.handle_wake_word(text)
                                elif self.wakeword.lower() in text.lower():
                                    self.wakeword_detected = True
                                    await self.send_status("recording")
                                    following_text = text.lower().split(self.wakeword.lower(), 1)[1].strip()
                                    if following_text:
                                        await self.handle_wake_word(following_text)
                    else:
                        print("is paused...")
                        await asyncio.sleep(0.5)
            except KeyboardInterrupt:
                print("\nStopping...")
        else: # NON-CONTINUOUS MODE
            await self.send_status("listening")
            self.start_stream()
            vad = self.vad
            sample_rate = self.sample_rate
            frame_duration = 30  # ms, must be 10, 20, or 30 for webrtcvad
            frame_bytes = int(sample_rate * frame_duration / 1000) * 2  # 2 bytes per sample (16-bit)
            silence_frames = int(self.settings.get("silence_frames", 1500) / frame_duration) 
            max_frames = int(10000 / frame_duration)  # 10 seconds max
            
            while True:
                if self.recording:
                    audio_buffer = []
                    silence_counter = 0
                    speech_started = False
                    speech_frames = 0
                    frame_count = 0
                    min_frames = int(1000 / frame_duration)  # Minimum 1 second of recording
                    
                    print("Starting recording in non-continuous mode with VAD")
                    recording_start = time.time()
                    max_recording_time = self.settings.get("max_recording_time", False)  # Changed from 7 to 60 seconds maximum
                    
                    # Process audio with both approaches
                    while self.recording and (time.time() - recording_start) < max_recording_time:
                        # Read a full chunk for buffer
                        chunk_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                        if len(chunk_data) == 0:
                            continue
                            
                        # Store the data in our buffer regardless of VAD
                        audio_buffer.append(chunk_data)
                        
                        # Process VAD on smaller frames
                        # We need to process frame_bytes sized chunks for VAD
                        for i in range(0, len(chunk_data) - frame_bytes + 1, frame_bytes):
                            frame = chunk_data[i:i+frame_bytes]
                            if len(frame) == frame_bytes:  # Ensure frame is complete
                                frame_count += 1
                                try:
                                    is_speech = vad.is_speech(frame, sample_rate)
                                    if is_speech:
                                        speech_started = True
                                        speech_frames += 1
                                        silence_counter = 0
                                    elif speech_started:
                                        silence_counter += 1
                                except Exception as e:
                                    # Just log and continue on VAD errors
                                    print(f"VAD error: {e}")
                                
                                # Check if we've recorded enough and detected end of speech
                                if (speech_started and 
                                    silence_counter >= silence_frames and 
                                    frame_count > min_frames):
                                    print(f"Detected end of speech after {silence_counter} silent frames")
                                    break
                        
                        # If we detected silence after min duration, break the outer loop too
                        if (speech_started and 
                            silence_counter >= silence_frames and 
                            frame_count > min_frames):
                            break
                            
                        await asyncio.sleep(0.01)
                    
                    # Process recorded audio
                    if len(audio_buffer) > 0:
                        await self.send_status("listening")
                        self.recording = False
                        print(f"Processing audio: {len(audio_buffer)} chunks, speech detected: {speech_started}")
                        self.save_audio_to_file(audio_buffer)
                        text = await self.transcribe_audio()
                        
                        # Always stop recording after processing
                        self.recording = False
                        await self.send_status("listening")
                        
                        if text:
                            print(f"Recognized text: {text}")
                            await self.handle_wake_word(text)
                        else:
                            print("No text recognized from audio")
                    else:
                        print("No audio recorded")
                        self.recording = False
                        await self.send_status("listening")
                else:
                    await asyncio.sleep(0.1)

    def process_incoming_message(self, message):
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
                else:
                    # If not an ASR-specific action, let the base plugin handle it
                    super().process_incoming_message(message)
        except json.JSONDecodeError:
            print("Received invalid JSON message")

    async def restart_with_new_mode(self):
        """Restart ASR with the new mode settings"""
        try:
            # Stop current processing
            if hasattr(self, 'stream') and self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if hasattr(self, 'p') and self.p:
                self.p.terminate()
            
            # Reset states
            self.is_paused = False
            self.recording = False
            self.wakeword_detected = False
            
            # Send status update before restarting
            await self.send_status("ready")
            
            # Restart with new mode
            await self.start()
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
            result = await loop.run_in_executor(None, self._transcribe_with_groq)
            return result
        except Exception as e:
            self.logger.error(f"Error transcribing audio: {e}")
            return ""
            
    def _transcribe_with_groq(self):
        """Helper method to run Groq transcription in a separate thread"""
        try:
            with open(self.temp_audio_file, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model,
                    language=self.lang  # Use the processed global language
                )
                return transcription.text
        except Exception as e:
            self.logger.error(f"Groq transcription error: {e}")
            return ""