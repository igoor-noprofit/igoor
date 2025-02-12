from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
import threading
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
        self.settings = self.get_my_settings()
        print ("ELEVENLABS settings", self.settings)
        try:
            self.user = User(self.settings.get("api_key"))
            self.voice= self.user.get_voice_by_ID(self.settings.get("voice_id"))   
            self.generation_options = self.settings.get("GenerationOptions")
            self.is_loaded = True
            # self.input_streamer=ReusableInputStreamer(self.voice)
        except Exception as e:
            print(f"Error occurred while setting user : {e}")
            return False
        
    @hookimpl
    def speak(self, message):
        print("§§§§ SPEAKING *********************************************** :", message)
        
        # Schedule the speak_func to run in the background
        asyncio.create_task(self.run_speak_func(message))

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())
        
    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func(self, message):
        success = await self.safe_speak_func(message)

    async def safe_speak_func(self, message):
        try:
            result = await self.speak_func(message)
            if not result:
                print("Speak function encountered an issue but handled gracefully.")
                await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    async def speak_func(self, message):
        print("SPEAK FUNC:" + message)
        try:
            # Set generation options
            playback_options = PlaybackOptions(
                runInBackground=False,
                onPlaybackEnd=self.run_restart_asr
            )
            generation_options = GenerationOptions(
                model_id=self.settings.get("model_id"),
                latencyOptimizationLevel=0,
                stability=0.65,
                similarity_boost=0.4,
                style=0.8
            )
            # websocket_options = WebsocketOptions(chunk_length_schedule=[125],try_trigger_generation=False)
            # Check if stream_audio_v3 is async
            # result = self.voice.stream_audio_v3(message, playback_options=playback_options, generation_options=generation_options, websocket_options=websocket_options)
            try:
                audio_future, generation_info_future = self.voice.generate_audio_v3(message, generation_options)
                generation_info = generation_info_future.result()
                audio_data = audio_future.result()
            except Exception as inner_e:
                print(f"Error retrieving audio data: {inner_e}")
                await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
                return True    
            # Play it back
            await self.pm.trigger_hook(hook_name="pause_asr")
            play_audio_v2(audio_data)
            self.run_restart_asr()
            return True

        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            await self.pm.trigger_hook(hook_name="speak_fallback",message=message) 
            return False