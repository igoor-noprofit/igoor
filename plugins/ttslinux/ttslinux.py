from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from fastapi import APIRouter
from pydantic import BaseModel
import asyncio
import io
import shutil
import subprocess
import threading
import wave


class SetVoicePayload(BaseModel):
    voice_id: int
    fallback_only: bool
    rate: int = 175


class Ttslinux(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.is_loaded = False
        self.fallback_only = False
        self.voice_id = 0
        self.rate = 175
        self._espeak_bin = shutil.which("espeak-ng")
        if self._espeak_bin is None:
            self.logger.warning("ttslinux: espeak-ng not found (apt install espeak-ng) — plugin loaded but inactive")
            return
        self.fallback_only = self.settings.get("fallback_only", False)
        self.voice_id = self.settings.get("voice_id", 0)
        self.rate = self.settings.get("rate", 175)
        # espeak-ng processes must never overlap on the same audio device.
        self._speak_lock = threading.Lock()
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
            self.logger.error(f"ERROR: No available voices for TTS LINUX: {e}")
            self.is_loaded = False

    def _enumerate_voices(self):
        """List espeak-ng voices as [{voice_id, voice_label, lang, identifier}],
        app-language voices first. The Language column is the documented `-v`
        selector, so it is used as the identifier; VoiceName is recovered
        best-effort for the dropdown label (it is a free-width column)."""
        app_lang_prefix = getattr(self, "lang", "en_EN").split("_")[0].lower()
        entries = []
        result = subprocess.run([self._espeak_bin, "--voices"], capture_output=True, text=True, timeout=30)
        for line in result.stdout.splitlines():
            tokens = line.split()
            if len(tokens) < 4 or not tokens[0].isdigit():
                continue  # header / blank lines
            lang = tokens[1]
            # Row layout: "Pty Language Age/Gender VoiceName File Other
            # Languages". Every row ends with parenthesized Other-Languages
            # groups ("(none 2)", "(en 5)(en-gb 10)"), so scanning from the
            # right for "(" locates the File column, and the free-width
            # VoiceName is what lies between Age/Gender and File.
            file_index = len(tokens) - 1
            for index in range(len(tokens) - 1, 2, -1):
                if tokens[index].startswith("("):
                    file_index = index - 1
                    break
            name = " ".join(tokens[3:file_index]) or lang
            entries.append({
                "voice_id": 0,  # renumbered below
                "voice_label": f"{name} ({lang})",
                "lang": lang,
                "identifier": lang,
                "_lang_match": lang.split("-")[0] == app_lang_prefix,
            })
        if not entries:
            raise RuntimeError(f"espeak-ng --voices returned no parseable voice: {result.stdout!r}")
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

    def _voice_identifier(self):
        if 0 <= self.voice_id < len(self.available_voices):
            return self.available_voices[self.voice_id]["identifier"]
        return None

    def _espeak_args(self):
        """Common flags: rate (-s, words/minute) and voice (-v, espeak voice file)."""
        args = [self._espeak_bin, "-s", str(self.rate)]
        identifier = self._voice_identifier()
        if identifier:
            args += ["-v", identifier]
        return args

    def _speak_timeout(self, message):
        words = max(1, len(message.split()))
        return words / max(80, self.rate) * 60 + 15

    def _speak_sync(self, message):
        """Blocking speak on the machine: espeak-ng synthesizes and plays through
        PulseAudio/ALSA in one call (called via asyncio.to_thread)."""
        with self._speak_lock:
            try:
                result = subprocess.run(
                    self._espeak_args() + [message],
                    capture_output=True, timeout=self._speak_timeout(message)
                )
                if result.returncode != 0:
                    self.logger.error(f"ttslinux: espeak-ng failed: {result.stderr.decode(errors='replace').strip()}")
                    return False
                return True
            except subprocess.TimeoutExpired:
                self.logger.warning("ttslinux: speak timed out, audio truncated")
                return False

    def _synthesize_bytes(self, message):
        """Render the message to raw PCM for browser streaming: espeak-ng writes
        a WAV to stdout, parsed here with the stdlib wave module.
        Returns (pcm_frames, sample_rate) or (None, 0) on any failure."""
        with self._speak_lock:
            try:
                result = subprocess.run(
                    self._espeak_args() + ["--stdout", message],
                    capture_output=True, timeout=self._speak_timeout(message)
                )
                if result.returncode != 0 or not result.stdout:
                    self.logger.error(f"ttslinux: espeak-ng synthesis failed: {result.stderr.decode(errors='replace').strip()}")
                    return None, 0
                with wave.open(io.BytesIO(result.stdout), "rb") as w:
                    channels = w.getnchannels()
                    width = w.getsampwidth()
                    rate = w.getframerate()
                    pcm = w.readframes(w.getnframes())
                if channels != 1 or width != 2 or not pcm:
                    self.logger.warning(f"ttslinux: unexpected WAV format (channels={channels}, width={width}) - not streaming")
                    return None, 0
                return pcm, rate
            except subprocess.TimeoutExpired:
                self.logger.warning("ttslinux: synthesis timed out")
                return None, 0

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/ttslinux", tags=["ttslinux"])

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
        self.logger.info("Global settings updated, refreshing ttslinux settings")
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

    @hookimpl
    def tts_playback_finished(self):
        """Releases wait_playback_finished after the browser acked playback,
        so ASR restarts immediately instead of after the 30s timeout."""
        self._on_playback_finished()

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
            # espeak-ng can render audio bytes: stream them to the browser
            # (headless setups have no reachable local speakers).
            pcm, rate = await asyncio.to_thread(self._synthesize_bytes, message)
            if pcm:
                streamed = await self.stream_audio_to_frontend([pcm], f"audio/pcm16;rate={rate}")
                if streamed:
                    return True
            self.logger.warning("ttslinux: no browser connected - speaking on machine speakers")
        try:
            return await asyncio.to_thread(self._speak_sync, message)
        except Exception as e:
            self.logger.error(f"Error occurred while speaking: {e}")
            return False
