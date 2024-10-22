from plugin_manager import hookimpl
from elevenlabslib import *
from dotenv import load_dotenv
load_dotenv()
import os
import pyaudio
from typing import Any, Dict

class Elevenlabs:
    @hookimpl
    def get_frontend_components(self):
        print("loading ELEVENLABS frontend")
        return [
            {
                "vue": "geo_component.vue"
            }
        ]
        
    @hookimpl
    def startup(self):
        print ("ELEVENLABS IS STARTING UP")
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID")
        # self.speak("Bonjour, je suis IGOOR!")

    @hookimpl
    def speak(self, message):
        try:
            user = User(self.api_key)
            print("VOICE ID ", self.voice_id)
            # print("AVAILABLE VOICES ", user.get_available_voices())
            voice=user.get_voice_by_ID(os.getenv("ELEVENLABS_VOICE_ID"))   
            print ("§§§§ SPEAKING *********************************************** :",message)
            # Set generation options
            playback_options = PlaybackOptions(runInBackground=True)
            generation_options = GenerationOptions(  # Adjusts latency optimization
                model_id=self.model_id, # Specifies the model
                latencyOptimizationLevel=1,
                stability=0.42,
                similarity_boost=0.4,
                style=0.8
            )
            voice.stream_audio_v3(message, playback_options, generation_options)
            return True
        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            return False
    
    def update_setting(self, key: str, value: Any):
        # Update using manager function
        self.plugin_manager.update_plugin_settings(self.plugin_name, key=key, value=value)

    def get_settings(self) -> dict:
        # Retrieving specific settings
        return self.settings