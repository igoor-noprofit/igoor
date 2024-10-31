from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
import threading
import time
import pyaudio
import json
import os, sys
from vosk import Model, KaldiRecognizer

class Asrvosk(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        print ("ASRVOSK IS REALLY STARTING UP")
        self.settings = self.get_my_settings()
        self.isloaded = False
        self.wakeword = self.settings.get("wakeword")
        print ("VOSK settings", self.settings)
        # Start a thread to load the model
        # self.model_thread = threading.Thread(target=self.load_model, daemon=True)
        # self.model_thread.start()
        # print("Started loading model in background.")
        # Optionally: Setup a monitor to check when the model is ready
        # monitor_thread = threading.Thread(target=self.monitor_loading, daemon=True)
        # monitor_thread.start()
        self.load_model()
        self.start()

    def monitor_loading(self):
        while not self.isloaded:
            # Wait until the model is loaded
            import time
            time.sleep(1)
        self.model_thread.join()
        print("Model is ready to use.")
        self.start()
    
    def load_model(self):
        global model, rec
        start_time = time.time()
        model_path = os.path.join(self.plugin_folder,"models",self.settings.get("lang"),self.settings.get("model_size"))
        model = Model(model_path)
        rec = KaldiRecognizer(model, 16000)
        elapsed_time = time.time() - start_time
        print(f"Model loaded in {elapsed_time:.2f} seconds.")
        self.isloaded = True
    
    def handle_wake_word(self,following_text):
        print(f"Wake word detected! Text: '{following_text}'")
        self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + following_text)
        
    def start(self):
        print("STARTING WAKEWORD RECOGNITION")
        # Initialize PyAudio and start the audio stream (after model loading)
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        self.stream.start_stream()
        try:
            while True:
                data = self.stream.read(4000, exception_on_overflow=False)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    text = json.loads(result)["text"]
                    print(f"Recognized text (FR): {text}")
                    if self.wakeword.lower() in text.lower():
                        following_text = text.lower().split(self.wakeword.lower(), 1)[1].strip()
                        self.handle_wake_word(following_text)
                        
        except KeyboardInterrupt:
            print("\nStopping...")
    
    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        
        

