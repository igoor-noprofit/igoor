from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import threading
import time
import pyaudio
import json
import time
import os, asyncio
from vosk import Model, KaldiRecognizer
from utils import setup_logger
import urllib.request
import zipfile

class Asrvosk(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.is_paused = False
        self.recording = False  # Initialize recording state
        self.is_loaded = False  # Make sure this is initialized
        self.wakeword_detected = False  # Initialize wakeword state
        super().__init__(plugin_name, pm)
        
    @hookimpl
    def startup(self):
        print ("ASRVOSK IS STARTING UP")
        self.settings = self.get_my_settings()
        self.wakeword = self.settings.get("wakeword")
        self.continuous = self.settings.get("continuous")
        print ("VOSK settings", self.settings)
        # Start a thread to load the model
        self.model_thread = threading.Thread(target=self.load_model, daemon=True)
        self.model_thread.start()
        print("Started loading model in background.")
        # Optionally: Setup a monitor to check when the model is ready
        # asyncio.run_coroutine_threadsafe(self.monitor_loading(), asyncio.get_event_loop())
        monitor_thread = threading.Thread(target=self.run_monitor_loading, daemon=True)
        monitor_thread.start()
    
    @hookimpl
    async def pause_asr(self):
        self.is_paused = True
        await(self.send_status("paused"))
        
    @hookimpl
    async def abandon_conversation(self, cause="timeout"):
        try:
            print("ASRVOSK received ABANDON_CONVERSATION trigger")
            # Your existing logic here
            self.wakeword_detected = False
            await self.send_status("listening")
            print("ASRVOSK after_conversation_end completed successfully")
        except Exception as e:
            print(f"Error in ASRVOSK after_conversation_end: {e}")
    
    '''
    To support external wakeword mechanism
    '''
    @hookimpl
    def wakeword_detected(self):
        self.wakeword_detected = True
        
        
    @hookimpl
    async def change_view(self,lastview,currentview):
        print("CHANGE VIEW IN ASRVOSK")
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
        global model, rec
        start_time = time.time()
        model_path = os.path.join(self.plugin_folder, "models", self.settings.get("lang"), self.settings.get("model_size"))
        
        self.logger.info(f"Attempting to load model from: {model_path}")
        
        # Check if model directory exists
        if not os.path.exists(model_path) or not os.listdir(model_path):
            self.logger.warning(f"Model not found at {model_path}, attempting to download...")
            try:
                # Load vosk_models.json
                source_dir = os.path.dirname(os.path.abspath(__file__))
                vosk_models_path = os.path.join(source_dir, "vosk_models.json")
                self.logger.debug(f"Loading models database from: {vosk_models_path}")
                
                with open(vosk_models_path, "r") as f:
                    models_db = json.load(f)
                
                # Get download URL based on language and size
                lang = self.settings.get("lang")
                size = self.settings.get("model_size")
                self.logger.info(f"Looking for model with lang={lang}, size={size}")
                
                model_info = models_db[lang][size]
                download_url = model_info["url"]
                self.logger.info(f"Found model URL: {download_url}")
                
                # Create necessary directories
                os.makedirs(model_path, exist_ok=True)
                self.logger.debug(f"Created directory structure: {model_path}")
                
                # Download and extract the model
                temp_zip = os.path.join(os.path.dirname(model_path), "temp_model.zip")
                self.logger.info(f"Downloading model to temporary file: {temp_zip}")
                urllib.request.urlretrieve(download_url, temp_zip)
                
                self.logger.info("Extracting model...")
                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    # Get the name of the first directory in the zip file
                    zip_root_dir = zip_ref.namelist()[0].split('/')[0]
                    # Extract to temporary location
                    temp_extract = os.path.dirname(model_path)
                    zip_ref.extractall(temp_extract)
                    
                    # Move contents from extracted folder to desired location
                    extracted_path = os.path.join(temp_extract, zip_root_dir)
                    if os.path.exists(model_path):
                        import shutil
                        shutil.rmtree(model_path)
                    os.rename(extracted_path, model_path)
                
                # Remove temporary zip file
                os.remove(temp_zip)
                self.logger.info("Model downloaded and extracted successfully")
                
            except Exception as e:
                self.logger.error(f"Error downloading model: {str(e)}", exc_info=True)
                raise
            
        try:
            # Load the model
            self.logger.info(f"Loading model from {model_path}")
            model = Model(model_path)
            rec = KaldiRecognizer(model, 16000)
            elapsed_time = time.time() - start_time
            self.logger.info(f"Model loaded successfully in {elapsed_time:.2f} seconds")
            self.is_loaded = True
        except Exception as e:
            self.logger.error(f"Error loading model: {str(e)}", exc_info=True)
            raise
    
    async def handle_wake_word(self,following_text):
        print(f"Wake word detected! Text: '{following_text}'")
        await self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=following_text, author="def",msg_input="vosk")
        await self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + following_text)

    async def start(self):
        if (self.continuous):
            self.wakeword_detected=False
            print("STARTING WAKEWORD RECOGNITION")
            await self.send_status("listening")
            # Initialize PyAudio and start the audio stream (after model loading)
            self.start_stream()
            try:
                while True:
                    if not self.is_paused:
                        data = self.stream.read(4000, exception_on_overflow=False)
                        if len(data) == 0:
                            break
                        if rec.AcceptWaveform(data):
                            result = rec.Result()
                            text = json.loads(result)["text"]
                            if text:
                                print(f"Recognized text (FR): {text}")
                                if self.wakeword_detected and text != "":
                                    await self.handle_wake_word(text)
                            if self.wakeword.lower() in text.lower():
                                self.wakeword_detected=True
                                await self.send_status("recording")
                                following_text = text.lower().split(self.wakeword.lower(), 1)[1].strip()
                                if (following_text != ""):
                                    await self.handle_wake_word(following_text)
                    else:
                        print("is paused...")
                        await asyncio.sleep(0.5)
            except KeyboardInterrupt:
                print("\nStopping...")
        else:
            await self.send_status("listening")
            self.start_stream()
            while True:
                if self.recording:
                    data = self.stream.read(4000, exception_on_overflow=False)
                    if len(data) == 0:
                        break
                    if rec.AcceptWaveform(data):
                        result = rec.Result()
                        text = json.loads(result)["text"]
                        if text:
                            print(f"Recognized text: {text}")
                            await self.handle_wake_word(text)
                            # After processing text, stop recording
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