from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import win32com.client


class SetVoicePayload(BaseModel):
    voice_id: int
    fallback_only: bool

class Ttsdefault(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        # Initialize SAPI
        self.fallback_only = self.settings.get("fallback_only", False)
        self.voice_id = self.settings.get("voice_id", 0)
        try:
            self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
            voices = self.speaker.GetVoices()
            self.available_voices = []
            self.logger.info("AVAILABLE VOICES:")
            for index, voice in enumerate(voices):
                description = voice.GetDescription()
                self.logger.info(f"- {description}")
                parts = description.split(' - ', 1)
                lang = parts[1] if len(parts) > 1 else ''
                self.available_voices.append({
                    "voice_id": index,
                    "voice_label": description,
                    "lang": lang
                })

                print(self.available_voices)
            
            self.is_loaded = True
            self.update_my_settings("voice_list", self.available_voices)
        except Exception as e:
            self.logger.error(f"ERROR: No available voices for TTS DEFAULT: {e}")
            self.is_loaded = False

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/ttsdefault", tags=["ttsdefault"])

        @self.router.post("/set_voice")
        async def set_voice(payload: SetVoicePayload):
            """Set voice ID and fallback_only mode immediately"""
            try:
                self.logger.info(f"Setting voice: voice_id={payload.voice_id}, fallback_only={payload.fallback_only}")

                # Update instance variables immediately
                self.voice_id = payload.voice_id
                self.fallback_only = payload.fallback_only

                # Update settings file
                self.update_my_settings("voice_id", payload.voice_id)
                self.update_my_settings("fallback_only", payload.fallback_only)

                # Update SAPI speaker voice if loaded
                if self.is_loaded:
                    try:
                        self.speaker.Voice = self.speaker.GetVoices().Item(self.voice_id)
                    except Exception as e:
                        self.logger.error(f"Error setting voice to {self.voice_id}: {e}")
                        return {"status": "error", "message": f"Failed to set SAPI voice: {str(e)}"}

                return {"status": "success", "voice_id": self.voice_id, "fallback_only": self.fallback_only}
            except Exception as e:
                self.logger.error(f"Error in set_voice endpoint: {e}")
                return {"status": "error", "message": str(e)}
                
    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        if plugin_name == self.plugin_name:
            self.logger.info(f"Settings updated for {plugin_name}: {new_settings}")
            self.settings = new_settings
            self.fallback_only = new_settings.get("fallback_only", False)
            self.voice_id = new_settings.get("voice_id")
            if self.is_loaded:
                try:
                    self.speaker.Voice = self.speaker.GetVoices().Item(self.voice_id)
                except Exception as e:
                    self.logger.error(f"Error setting voice to {self.voice_id}: {e}")

    @hookimpl
    def global_settings_updated(self):
        self.logger.info("Global settings updated, refreshing ttsdefault settings")
        self.settings = self.get_my_settings()
        self.fallback_only = self.settings.get("fallback_only", False)
        self.voice_id = self.settings.get("voice_id", 0)
        if self.is_loaded:
            try:
                self.speaker.Voice = self.speaker.GetVoices().Item(self.voice_id)
            except Exception as e:
                self.logger.error(f"Error setting voice to {self.voice_id}: {e}")

    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

        if self.is_loaded:
            try:
                self.speaker.Voice = self.speaker.GetVoices().Item(self.voice_id)
                self.mark_ready()
            except Exception as e:
                print(f"Error occurred while setting voice to : {self.voice_id}")
                self.speaker.Voice = self.speaker.GetVoices().Item(0)
                return False   
    
    '''
    @hookimpl
    def test_speak(self, message, **kwargs):
        self.get_my_settings()
        voice_id = kwargs.get('voice_id', self.voice_id)
        print(f"TEST SPEAK with pitch={pitch}, rate={rate}, volume={volume}")
        self.speak(message)
    '''
        
    @hookimpl
    def speak(self, message):
        if self.is_loaded and not self.fallback_only:
            self.logger.info("§§§§ SPEAKING *********************************************** : %s", message)
            # Schedule the speak_func to run in the background
            asyncio.create_task(self.run_speak_func(message))

    @hookimpl
    def speak_fallback(self, message):
        self.logger.info("§§§§ FALLBACK SPEAKING *********************************************** : %s", message)
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
        await asyncio.sleep(0.1)  # Ensure pause message reaches frontend
        success = await self.speak_func(message)
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def speak_func(self, message):
        self.logger.info("SPEAK FUNC:" + message)
        try:
            # Note: SAPI COM objects are thread-affine, cannot use asyncio.to_thread
            self.speaker.Speak(message)
            return True

        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            return False