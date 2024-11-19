from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
from elevenlabslib import *
from elevenlabslib.helpers import play_audio_v2
from typing import Any, Dict
from settings_manager import SettingsManager
import asyncio

class Elevenlabs(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
                
    @hookimpl
    def startup(self):
        print ("ELEVENLABS IS STARTING UP")
        self.settings = self.get_my_settings()
        print ("ELEVENLABS settings", self.settings)
        try:
            self.user = User(self.settings.get("api_key"))
            self.voice= self.user.get_voice_by_ID(self.settings.get("voice_id"))   
        except Exception as e:
            print(f"Error occurred while setting user : {e}")
            return False
        
    @hookimpl
    def speak(self, message):
        print("§§§§ SPEAKING *********************************************** :", message)
        
        # Schedule the speak_func to run in the background
        asyncio.create_task(self.run_speak_func(message))

    async def run_speak_func(self, message):
        success = await self.speak_func(message)
        
        if success:
            await self.pm.trigger_hook(hook_name="restart_asr")
            print("Speaking is done.")
        else:
            print("Speaking failed.")

    async def speak_func(self, message):
        await self.pm.trigger_hook(hook_name="pause_asr")
        print("SPEAK FUNC:" + message)
        try:
            # Set generation options
            playback_options = PlaybackOptions(runInBackground=True)
            generation_options = GenerationOptions(
                model_id=self.settings.get("model_id"),
                latencyOptimizationLevel=0,
                stability=0.42,
                similarity_boost=0.4,
                style=0.8
            )
            # Check if stream_audio_v3 is async
            # result = self.voice.stream_audio_v3(message, playback_options, generation_options)
            audio_future, generation_info_future = self.voice.generate_audio_v3(message, generation_options)
            generation_info = generation_info_future.result()
            audio_data = audio_future.result()
            # Play it back
            play_audio_v2(audio_data)
            return True

            return True
        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            return False