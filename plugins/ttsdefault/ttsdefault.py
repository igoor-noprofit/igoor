from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
import asyncio
import win32com.client

class Ttsdefault(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        # Initialize SAPI
        self.fallback_only = self.settings.get("fallback_only")
        self.speaker_voice = self.settings.get("speaker_voice")
        try:
            self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
            voices = self.speaker.GetVoices()
            self.available_voices = []
            self.logger.info("AVAILABLE VOICES:")
            for voice in voices:
                description = voice.GetDescription()
                self.logger.info(f"- {description}")
                parts = description.split(' - ', 1)
                voice_id = parts[0]
                lang = parts[1] if len(parts) > 1 else ''
                self.available_voices.append({"voice_id": voice_id, "lang": lang})
            
            self.is_loaded = True
            self.update_my_settings("voice_list", self.available_voices)
        except Exception as e:
            self.logger.error(f"ERROR: No available voices for TTS DEFAULT: {e}")
            self.is_loaded = False    
                
    @hookimpl
    def startup(self):
        if self.is_loaded:
            try:
                self.speaker.Voice = self.speaker.GetVoices().Item(self.speaker_voice)
            except Exception as e:
                print(f"Error occurred while setting voice to : {self.speaker_voice}")
                self.speaker.Voice = self.speaker.GetVoices().Item(0)
                return False   
        
    @hookimpl
    def speak(self, message):
        if self.is_loaded and not self.fallback_only:
            self.logger.info("§§§§ SPEAKING *********************************************** :", message)
            # Schedule the speak_func to run in the background
            asyncio.create_task(self.run_speak_func(message))

    @hookimpl
    def speak_fallback(self, message):
        self.logger.info("§§§§ FALLBACK SPEAKING *********************************************** : {message}")
        # Schedule the speak_func to run in the background
        if (self.fallback_only):
            asyncio.create_task(self.run_speak_func(message))
            
    @hookimpl
    def speak_as_igoor(self, message):
        self.logger.info(f"§§§§ SPEAKING AS IGOOR *********************************************** : {message}")
        # Used to speak as the machine
        asyncio.create_task(self.run_speak_func(message))

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())
        
    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func(self, message):
        await self.pm.trigger_hook(hook_name="pause_asr")
        success = await self.speak_func(message)
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def speak_func(self, message):
        self.logger.info("SPEAK FUNC:" + message)
        try:
            self.speaker.Speak(message)
            return True

        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            return False