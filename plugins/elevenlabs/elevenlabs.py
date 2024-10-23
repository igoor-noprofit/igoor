from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from elevenlabslib import *
from dotenv import load_dotenv
load_dotenv()
import os
import pyaudio
from typing import Any, Dict
from settings_manager import SettingsManager

class Elevenlabs(Baseplugin):        
    @hookimpl
    def startup(self):
        super().__init__('elevenlabs')
        print ("ELEVENLABS IS STARTING UP")
        self.settings = self.get_my_settings()
        print ("ELEVENLABS settings", self.settings)
        self.speak("Bonjour, je suis IGOOR!")

    @hookimpl
    def speak(self, message):
        try:
            user = User(self.settings.api_key)
            print("VOICE ID ", self.settings.voice_id)
            voice=user.get_voice_by_ID(self.settings.voice_id)   
            print ("§§§§ SPEAKING *********************************************** :",message)
            # Set generation options
            playback_options = PlaybackOptions(runInBackground=True)
            generation_options = GenerationOptions(  # Adjusts latency optimization
                model_id=self.settings.model_id, # Specifies the model
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
