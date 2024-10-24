from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl 
import threading
import time
import pyaudio
import json
import os
from vosk import Model, KaldiRecognizer
import sys

class Sttvosk(Baseplugin):
    @hookimpl
    def startup(self):
        super().__init__('sttvosk')
        print ("STTVOSK IS STARTING UP")
        self.settings = self.get_my_settings()
        self.isloaded = False
        print ("VOSK settings", self.settings)
        # Start a thread to load the model
                # Start a thread to load the model
        model_thread = threading.Thread(target=self.load_model, daemon=True)
        model_thread.start()
        print("Started loading model in background.")

        # Optionally: Setup a monitor to check when the model is ready
        monitor_thread = threading.Thread(target=self.monitor_loading, daemon=True)
        monitor_thread.start()

        # Continue with other initialization or setup here, if needed
        # You can check if the model is ready and start streaming when it is

        # Wait for the model to finish loading before starting the audio stream
        model_thread.join()

    
    def monitor_loading(self):
        while not self.isloaded:
            # Wait until the model is loaded
            import time
            time.sleep(1)
        
        # Assume you have some mechanism to update UI or the state when loaded
        print("Model is ready to use.")
        self.isloaded = True
    
    def load_model(self):
        global model, rec
        start_time = time.time()
        model_path = os.path.join(self.plugin_folder,"models",self.settings.get("lang"),self.settings.get("model_size"))
        model = Model(model_path)
        rec = KaldiRecognizer(model, 16000)
        elapsed_time = time.time() - start_time
        
        print(f"Model loaded in {elapsed_time:.2f} seconds.")
    
    def handle_wake_word(self,following_text):
        print(f"Wake word detected! Following text: '{following_text}'")
    
    def start(self):
        
        # Initialize PyAudio and start the audio stream (after model loading)
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        self.stream.start_stream()
        wakeword = self.settings.get("wakeword")
        try:
            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    text = json.loads(result)["text"]
                    print(f"Recognized text (FR): {text}")
                    if wakeword.lower() in text.lower():
                        following_text = text.lower().split(wakeword.lower(), 1)[1].strip()
                        handle_wake_word(following_text)
                        
        except KeyboardInterrupt:
            print("\nStopping...")
    
    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        
        

