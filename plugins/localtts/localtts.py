from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
import threading
import asyncio
import json
import io
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import numpy as np
import sounddevice as sd
import soundfile as sf

from plugins.localtts.audio8_runtime import Audio8Runtime

MODEL_REPO = "Audio8/audio8-TTS-0.1B-ONNX-INT8"
MODEL_DIRNAME = "audio8-0.1b-int8"


class Localtts(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        self.runtime: Optional[Audio8Runtime] = None
        self.model_state = "not_downloaded"  # not_downloaded|downloading|loading|ready|error
        self.model_state_detail = ""
        self._init_lock = threading.Lock()
        self._init_started = False
        super().__init__(plugin_name, pm)

    # ── lifecycle ───────────────────────────────────────────────────────

    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        default_settings = {
            "voice": "default",
            "threads": 5,
            "temperature": 0.7,
            "max_new_tokens": 800,
        }
        changed = False
        for key, default_value in default_settings.items():
            if key not in self.settings:
                self.settings[key] = default_value
                changed = True
        if changed:
            self.update_my_settings("voice", self.settings.get("voice"))
        self._ensure_router()
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        # Download + load the model only for an activated plugin (this code
        # only runs for activated plugins, same as the sherpa model in asrjs)
        self._start_model_init()

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        if plugin_name != 'localtts':
            return
        old = dict(getattr(self, "settings", {}))
        self.settings = self.get_my_settings()
        # Re-initialize only when the loaded voice or thread count changed;
        # generation parameters are read at speak time and need no reload
        needs_reload = (
            self.model_state == "ready"
            and (
                old.get("voice") != self.settings.get("voice")
                or old.get("threads") != self.settings.get("threads")
            )
        )
        if needs_reload:
            self._start_model_init(force=True)

    @hookimpl
    def global_settings_updated(self):
        # Language changes need no reload: the model is multilingual and the
        # prompt language follows the text being spoken
        pass

    def _start_model_init(self, force=False):
        with self._init_lock:
            if self._init_started and not force:
                return
            self._init_started = True
        threading.Thread(target=self._init_worker, daemon=True).start()

    def _model_dir(self):
        return os.path.join(self.plugin_folder, "models", MODEL_DIRNAME)

    def _model_is_downloaded(self):
        return os.path.isfile(os.path.join(self._model_dir(), "runtime_manifest.json"))

    def _set_model_state(self, state, detail=""):
        self.model_state = state
        self.model_state_detail = detail
        self.logger.info(f"localtts model state: {state} {detail}")
        self.send_message_to_frontend({
            "type": "model_status",
            "state": state,
            "detail": detail,
            "voices": self._voice_list(),
        })

    def _init_worker(self):
        try:
            self.mark_not_ready()
            if not self._model_is_downloaded():
                self._set_model_state("downloading")
                from huggingface_hub import snapshot_download

                snapshot_download(
                    repo_id=MODEL_REPO,
                    local_dir=self._model_dir(),
                    token=False,  # public repo; avoids stale-token 401s
                )
            self._set_model_state("loading")
            runtime = Audio8Runtime(
                self._model_dir(),
                os.path.join(self.plugin_folder, "voices"),
                threads=int(self.settings.get("threads", 5)),
            )
            runtime._ensure_default_voice()
            # Prebuild the prefix cache for the configured voice so the first
            # utterance doesn't pay the ~4s prefill
            runtime.get_prefix_state(self.settings.get("voice", "default"))
            self.runtime = runtime
            self._set_model_state("ready")
            self.mark_ready()
        except Exception as e:
            self.logger.error(f"localtts model init failed: {e}")
            self.runtime = None
            self._set_model_state("error", str(e))

    # ── voices ──────────────────────────────────────────────────────────

    def _voice_list(self):
        if self.runtime is None:
            return []
        return [
            {"id": v.get("name"), "display_name": v.get("name")}
            for v in self.runtime.voices.list()
        ]

    def _send_voice_list(self):
        self.send_message_to_frontend({
            "type": "voice_list",
            "voice_list": self._voice_list(),
        })

    # ── REST router ─────────────────────────────────────────────────────

    def _ensure_router(self):
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/localtts", tags=["localtts"])

        @self.router.get("/status")
        async def status():
            return {
                "state": self.model_state,
                "detail": self.model_state_detail,
                "voices": self._voice_list(),
                "model_downloaded": self._model_is_downloaded(),
            }

        @self.router.post("/download_model")
        async def download_model():
            """Retry the download/init after a failure"""
            if self.model_state in ("downloading", "loading"):
                return {"status": "already_running"}
            self._start_model_init(force=True)
            return {"status": "started"}

        @self.router.post("/test_speak")
        async def test_speak(payload: dict):
            message = payload.get("message", "Hello, how are you doing? I feel better today!")
            try:
                await self._test_speak(message)
                return {"status": "success", "message": "Audio generated successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to test voice: {str(e)}")

        @self.router.post("/register_voice")
        async def register_voice(
            audio_file: UploadFile = File(...),
            text: str = Form(...),
            name: str = Form(...),
        ):
            try:
                if self.runtime is None:
                    raise HTTPException(status_code=400, detail="Model is not loaded yet")
                audio_bytes = await audio_file.read()
                if not audio_bytes:
                    raise HTTPException(status_code=400, detail="Empty audio file")
                meta = await asyncio.to_thread(
                    self.runtime.register_voice, audio_bytes, text, name
                )
                self._send_voice_list()
                return {"status": "created", "voice": meta.get("name")}
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error registering voice: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to register voice: {str(e)}")

    # ── websocket (settings UI) ─────────────────────────────────────────

    @hookimpl
    def on_websocket_message(self, message):
        try:
            data = json.loads(message)
            action = data.get("action")
            if action == "get_voice_list":
                self._send_voice_list()
            elif action == "test_speak":
                threading.Thread(
                    target=self._test_speak_local,
                    args=(data.get("message", "Hello, how are you doing?"),),
                    daemon=True,
                ).start()
        except Exception as e:
            self.logger.error(f"Error handling websocket message: {e}")
            self.send_error_to_frontend(str(e))

    # ── playback ────────────────────────────────────────────────────────

    def _play_audio(self, audio: np.ndarray):
        audio_array = np.clip(audio, -1.0, 1.0)
        audio_array = (audio_array * 32767).astype(np.int16)
        sd.play(audio_array, samplerate=self.runtime.sample_rate)
        sd.wait()

    def _wav_bytes(self, audio: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, np.clip(audio, -1.0, 1.0), self.runtime.sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()

    def _synthesize_current(self, message):
        return self.runtime.synthesize(
            text=message,
            voice=self.settings.get("voice", "default"),
            max_new_tokens=int(self.settings.get("max_new_tokens", 800)),
            temperature=float(self.settings.get("temperature", 0.7)),
        )

    async def _test_speak(self, message):
        if self.runtime is None or self.model_state != "ready":
            self.send_error_to_frontend("model_not_ready", "The local TTS model is not ready yet")
            return
        audio, _ = await asyncio.to_thread(self._synthesize_current, message)
        if self.is_remote_ui():
            wav = self._wav_bytes(audio)
            asyncio.get_running_loop().create_task(
                self.stream_audio_to_frontend([wav], "audio/wav")
            )
        else:
            await asyncio.to_thread(self._play_audio, audio)

    def _test_speak_local(self, message):
        """Sync settings preview for the websocket path (local playback only)"""
        if self.runtime is None or self.model_state != "ready":
            self.send_error_to_frontend("model_not_ready", "The local TTS model is not ready yet")
            return
        audio, _ = self._synthesize_current(message)
        self._play_audio(audio)

    # ── speak hook chain (mirrors elevenlabstts) ────────────────────────

    @hookimpl
    def speak(self, message, skip_asr):
        print("§§§§ LOCALTTS SPEAKING *********************************************** :", message)
        asyncio.create_task(self.run_speak_func_with_translation(message, skip_asr=skip_asr))
        asyncio.create_task(self.pm.trigger_hook(hook_name="reset_conversation_timeout"))

    @hookimpl
    def tts_playback_finished(self):
        self._on_playback_finished()

    def run_restart_asr(self, force_ready=False):
        asyncio.create_task(self.restart_asr(force_ready))

    async def restart_asr(self, force_ready=False):
        await self.pm.trigger_hook(hook_name="restart_asr", force_ready=force_ready)

    async def run_speak_func(self, message, skip_asr=False):
        await self.safe_speak_func(message, skip_asr=skip_asr)

    async def run_speak_func_with_translation(self, message, skip_asr=False):
        translated_message = await self.translate_for_interlocutor(message, direction="outgoing")
        await self.run_speak_func(translated_message, skip_asr=skip_asr)

    async def safe_speak_func(self, message, skip_asr=False):
        try:
            result = await self.speak_func(message, skip_asr=skip_asr)
            if not result:
                await self.call_fallback(message=message)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await self.call_fallback(message=message)

    async def speak_func(self, message, skip_asr=False):
        try:
            if self.runtime is None or self.model_state != "ready":
                self.logger.warning("localtts model not ready, cannot speak")
                return False
            self.settings = self.get_my_settings()
            # Pause ASR before synthesis: local generation takes seconds and
            # an open mic would feed back into the conversation
            await self.pm.trigger_hook(hook_name="pause_asr")
            await asyncio.sleep(0.1)
            audio, _ = await asyncio.to_thread(
                self.runtime.synthesize,
                text=message,
                voice=self.settings.get("voice", "default"),
                max_new_tokens=int(self.settings.get("max_new_tokens", 800)),
                temperature=float(self.settings.get("temperature", 0.7)),
            )
            if self.is_remote_ui():
                wav = self._wav_bytes(audio)
                streamed = await self.stream_audio_to_frontend([wav], "audio/wav")
                if not streamed:
                    await asyncio.to_thread(self._play_audio, audio)
            else:
                await asyncio.to_thread(self._play_audio, audio)
            self.run_restart_asr(force_ready=skip_asr)
            return True
        except Exception as e:
            print(f"Error occurred while speaking: {e}")
            return False

    async def call_fallback(self, message):
        await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
