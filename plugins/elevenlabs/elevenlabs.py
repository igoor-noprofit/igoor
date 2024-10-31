from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
from elevenlabslib import *
import pyaudio
from typing import Any, Dict
from settings_manager import SettingsManager

class Elevenlabs(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
                
    @hookimpl
    def startup(self):
        print ("ELEVENLABS IS STARTING UP")
        self.settings = self.get_my_settings()
        print ("ELEVENLABS settings", self.settings)
        
    @hookimpl
    def speak(self, message):
        try:
            user = User(self.settings.get("api_key"))
            voice=user.get_voice_by_ID(self.settings.get("voice_id"))   
            print ("§§§§ SPEAKING *********************************************** :",message)
            # Set generation options
            playback_options = PlaybackOptions(runInBackground=True)
            generation_options = GenerationOptions(  # Adjusts latency optimization
                model_id=self.settings.get("model_id"), # Specifies the model
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
