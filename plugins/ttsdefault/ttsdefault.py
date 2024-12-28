from plugin_manager import hookimpl, PluginManager
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
import asyncio
import win32com.client

class Ttsdefault(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
                
    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        # Initialize SAPI
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.fallback_only = self.settings.get("fallback_only")
        self.speaker_voice = self.settings.get("speaker_voice")
        try:
            self.speaker.Voice = self.speaker.GetVoices().Item(self.speaker_voice)
        except Exception as e:
            print(f"Error occurred while setting voice to : {self.speaker_voice}")
            self.speaker.Voice = self.speaker.GetVoices().Item(0)
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
        success = await self.speak_func(message)

    async def speak_func(self, message):
        print("SPEAK FUNC:" + message)
        try:
            self.speaker.Speak(message)
            return True

        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            return False