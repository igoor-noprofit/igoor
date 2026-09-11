from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import threading
import time
try:
    from AppKit import NSSpeechSynthesizer
except ImportError:
    # Windows/Linux: keep the plugin importable; macOS system TTS stays unavailable
    NSSpeechSynthesizer = None


class SetVoicePayload(BaseModel):
    voice_id: int
    fallback_only: bool
    rate: int = 175


class Ttsmac(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.is_loaded = False
        self.fallback_only = False
        self.voice_id = 0
        self.rate = 175
        if NSSpeechSynthesizer is None:
            self.logger.warning("ttsmac: macOS system TTS not available on this platform (AppKit missing) — plugin loaded but inactive")
            return
        self.fallback_only = self.settings.get("fallback_only", False)
        self.voice_id = self.settings.get("voice_id", 0)
        self.rate = self.settings.get("rate", 175)
        # Created lazily inside the speak worker thread: AppKit objects are
        # happiest when created and used from one thread, and the synthesizer
        # must never be shared by overlapping speak tasks.
        self._synth = None
        self._synth_lock = threading.Lock()
        try:
            self.available_voices = self._enumerate_voices()
            self.logger.info(f"AVAILABLE VOICES ({len(self.available_voices)}):")
            for v in self.available_voices[:10]:
                self.logger.info(f"- {v['voice_label']}")
            if len(self.available_voices) > 10:
                self.logger.info(f"- … and {len(self.available_voices) - 10} more")
            self.voice_id = self._sanitize_voice_id(self.voice_id)
            self.is_loaded = True
            self.update_my_settings("voice_list", self.available_voices)
        except Exception as e:
            self.logger.error(f"ERROR: No available voices for TTS MAC: {e}")
            self.is_loaded = False

    def _enumerate_voices(self):
        """List system voices as [{voice_id, voice_label, lang, identifier}],
        app-language voices first. Siri voices are filtered (flaky identifiers)."""
        app_lang_prefix = getattr(self, "lang", "en_EN").split("_")[0]
        entries = []
        for identifier in NSSpeechSynthesizer.availableVoices():
            ident = str(identifier)
            if "siri" in ident.lower():
                continue
            attrs = NSSpeechSynthesizer.attributesForVoice_(identifier)
            # Attribute keys are unprefixed ("VoiceName", not NSVoiceName)
            name = str(attrs.get("VoiceName") or ident.split(".")[-1])
            locale = str(attrs.get("VoiceLocaleIdentifier") or "")
            lang = locale.replace("-", "_")
            label = f"{name} ({lang})" if lang else name
            entries.append({
                "voice_id": 0,  # renumbered below
                "voice_label": label,
                "lang": lang,
                "identifier": ident,
                "_lang_match": lang.split("_")[0] == app_lang_prefix,
            })
        entries.sort(key=lambda v: (not v["_lang_match"], v["voice_label"]))
        for index, entry in enumerate(entries):
            entry["voice_id"] = index
            del entry["_lang_match"]
        return entries

    def _sanitize_voice_id(self, voice_id):
        """Keep the stored index inside the current voice list; an app-language
        voice is the sensible default when the stored one no longer resolves."""
        if self.available_voices and 0 <= voice_id < len(self.available_voices):
            return voice_id
        return 0

    def _get_synth(self):
        if self._synth is None:
            self._synth = NSSpeechSynthesizer.alloc().initWithVoice_(None)
        return self._synth

    def _voice_identifier(self):
        if 0 <= self.voice_id < len(self.available_voices):
            return self.available_voices[self.voice_id]["identifier"]
        return None

    def _apply_voice(self):
        identifier = self._voice_identifier()
        if identifier:
            self._get_synth().setVoice_(identifier)
        self._get_synth().setRate_(self.rate)

    def _speak_sync(self, message):
        """Blocking speak on the machine (called via asyncio.to_thread)."""
        with self._synth_lock:
            synth = self._get_synth()
            self._apply_voice()
            words = max(1, len(message.split()))
            timeout = words / max(80, self.rate) * 60 + 15
            if not synth.startSpeakingString_(message):
                self.logger.error("ttsmac: startSpeakingString returned False")
                return False
            start = time.time()
            while synth.isSpeaking() and time.time() - start < timeout:
                time.sleep(0.1)
            if synth.isSpeaking():
                synth.stopSpeaking()
                self.logger.warning("ttsmac: speak timed out, audio truncated")
                return False
            return True

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/ttsmac", tags=["ttsmac"])

        @self.router.post("/set_voice")
        async def set_voice(payload: SetVoicePayload):
            """Set voice ID, rate and fallback_only mode immediately"""
            try:
                self.logger.info(f"Setting voice: voice_id={payload.voice_id}, rate={payload.rate}, fallback_only={payload.fallback_only}")
                self.voice_id = self._sanitize_voice_id(payload.voice_id)
                self.rate = max(80, min(600, payload.rate))
                self.fallback_only = payload.fallback_only
                self.update_my_settings("voice_id", self.voice_id)
                self.update_my_settings("rate", self.rate)
                self.update_my_settings("fallback_only", self.fallback_only)
                return {"status": "success", "voice_id": self.voice_id, "rate": self.rate, "fallback_only": self.fallback_only}
            except Exception as e:
                self.logger.error(f"Error in set_voice endpoint: {e}")
                return {"status": "error", "message": str(e)}

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        if plugin_name == self.plugin_name:
            self.logger.info(f"Settings updated for {plugin_name}: {new_settings}")
            self.settings = new_settings
            self.fallback_only = new_settings.get("fallback_only", False)
            self.voice_id = self._sanitize_voice_id(new_settings.get("voice_id", 0))
            self.rate = max(80, min(600, new_settings.get("rate", 175)))

    @hookimpl
    def global_settings_updated(self):
        self.logger.info("Global settings updated, refreshing ttsmac settings")
        self.settings = self.get_my_settings()
        self.fallback_only = self.settings.get("fallback_only", False)
        self.voice_id = self._sanitize_voice_id(self.settings.get("voice_id", 0))
        self.rate = max(80, min(600, self.settings.get("rate", 175)))

    @hookimpl
    def startup(self):
        self._ensure_router()
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        if self.is_loaded:
            self.mark_ready()

    @hookimpl
    def speak(self, message, skip_asr):
        if self.is_loaded and not self.fallback_only:
            self.logger.info("§§§§ SPEAKING *********************************************** : %s", message)
            asyncio.create_task(self.run_speak_func_with_translation(message, skip_asr=skip_asr))

    @hookimpl
    def speak_fallback(self, message):
        self.logger.info("§§§§ FALLBACK SPEAKING *********************************************** : %s", message)
        if self.fallback_only:
            asyncio.create_task(self.run_speak_func(message))

    @hookimpl
    def speak_as_igoor(self, message):
        if not self.is_loaded:
            return
        self.logger.info(f"§§§§ SPEAKING AS IGOOR *********************************************** : {message}")
        asyncio.create_task(self.run_speak_func(message))

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())

    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr", force_ready=False)

    async def run_speak_func(self, message, skip_asr=False):
        await self.pm.trigger_hook(hook_name="pause_asr")
        await asyncio.sleep(0.1)  # Ensure pause message reaches frontend
        success = await self.speak_func(message)
        await self.pm.trigger_hook(hook_name="restart_asr", force_ready=skip_asr)

    async def run_speak_func_with_translation(self, message, skip_asr=False):
        """Translate outgoing speech before speaking"""
        translated_message = await self.translate_for_interlocutor(message, direction="outgoing")
        await self.run_speak_func(translated_message, skip_asr=skip_asr)

    async def speak_func(self, message):
        self.logger.info("SPEAK FUNC:" + message)
        if self.is_remote_ui():
            # The synthesizer plays on the Mac's speakers: it cannot be
            # streamed to the browser, even on the same machine.
            self.logger.warning("macOS system TTS cannot reach the browser - speaking on Mac speakers")
        try:
            return await asyncio.to_thread(self._speak_sync, message)
        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            return False
