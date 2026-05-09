from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi import Form
from pydantic import BaseModel
import asyncio
import os
import threading
import time
import json
import numpy as np
import sounddevice as sd

# ── Language mapping ────────────────────────────────────────────────────
IGOOR_LANG_TO_POCKETTTS = {
    "en_EN": "english",
    "en": "english",
    "fr_FR": "french",
    "fr": "french",
    "it_IT": "italian",
    "it": "italian",
    "de_DE": "german",
    "de": "german",
    "pt_BR": "portuguese",
    "pt_PT": "portuguese",
    "pt": "portuguese",
    "es_ES": "spanish",
    "es": "spanish",
}

# ── Built-in voice catalog ─────────────────────────────────────────────
# Sourced from the actual pocket-tts error message (complete list).
# Built-in voices work WITHOUT HuggingFace login.
# Note: voices are cross-language — any voice can be used with any language model.
BUILTIN_VOICES = {
    "english": [
        {"name": "alba", "label": "Alba"},
        {"name": "vera", "label": "Vera"},
        {"name": "george", "label": "George"},
        {"name": "mary", "label": "Mary"},
        {"name": "jane", "label": "Jane"},
        {"name": "michael", "label": "Michael"},
        {"name": "eve", "label": "Eve"},
        {"name": "anna", "label": "Anna"},
        {"name": "charles", "label": "Charles"},
        {"name": "paul", "label": "Paul"},
        {"name": "bill_boerst", "label": "Bill"},
        {"name": "peter_yearsley", "label": "Peter"},
        {"name": "stuart_bell", "label": "Stuart"},
        {"name": "caro_davy", "label": "Caro"},
    ],
    "french": [
        {"name": "estelle", "label": "Estelle"},
        {"name": "cosette", "label": "Cosette"},
        {"name": "marius", "label": "Marius"},
        {"name": "javert", "label": "Javert"},
        {"name": "jean", "label": "Jean"},
        {"name": "fantine", "label": "Fantine"},
        {"name": "eponine", "label": "Éponine"},
        {"name": "azelma", "label": "Azelma"},
    ],
    "italian": [
        {"name": "giovanni", "label": "Giovanni"},
    ],
    "german": [
        {"name": "juergen", "label": "Jürgen"},
    ],
    "portuguese": [
        {"name": "rafael", "label": "Rafael"},
    ],
    "spanish": [
        {"name": "lola", "label": "Lola"},
    ],
}

# Error key emitted by pocket-tts when voice cloning weights are not available
VOICE_CLONING_UNAVAILABLE_MSG = "VOICE_CLONING_UNSUPPORTED"
HF_CLONING_INSTRUCTIONS = (
    "Voice cloning requires accepting the terms on HuggingFace and logging in. "
    "Go to https://huggingface.co/kyutai/pocket-tts, accept the terms, "
    "then run: uvx hf auth login"
)

# Default voice per language (first voice in each list)
DEFAULT_VOICE = {
    "english": "alba",
    "french": "estelle",
    "italian": "giovanni",
    "german": "juergen",
    "portuguese": "rafael",
    "spanish": "lola",
}

# Languages that ONLY have a 24-layer model (no standard variant available)
# pocket-tts raises an error if you try to load these without the _24l suffix
REQUIRES_24L = {"french", "portuguese", "spanish"}


class TestSpeakPayload(BaseModel):
    message: str = "Hello, how are you doing? I feel better today!"


class HfLoginPayload(BaseModel):
    token: str


class Pockettts(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.router = None
        super().__init__(plugin_name, pm)
        self.tts_model = None
        self.voice_state = None
        self.model_language = None
        self._model_loading = False

    # ── Language helpers ────────────────────────────────────────────────

    def _resolve_language(self):
        """Map IGOOR locale (e.g. 'fr_FR') to pocket-tts language name."""
        lang = getattr(self, 'lang', None) or 'en_EN'
        return IGOOR_LANG_TO_POCKETTTS.get(lang, "english")

    # ── FastAPI router ──────────────────────────────────────────────────

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/pockettts", tags=["pockettts"])

        @self.router.get("/voices")
        async def get_voices():
            """Get available voices for the current language"""
            language = self._resolve_language()
            voices = BUILTIN_VOICES.get(language, [])
            custom_voices = self._get_custom_voices()
            return {
                "language": language,
                "builtin": voices,
                "custom": custom_voices,
                "current_voice": self.settings.get("voice", "auto")
            }

        @self.router.get("/model_status")
        async def model_status():
            """Return current model/voice loading status"""
            return {
                "model_loaded": self.tts_model is not None,
                "model_loading": self._model_loading,
                "language": self.model_language,
                "voice": self.settings.get("voice", "auto"),
                "is_ready": self.ready,
            }

        @self.router.post("/test_speak")
        async def test_speak(payload: TestSpeakPayload):
            """Test speech synthesis with current settings"""
            if self.tts_model is None or self.voice_state is None:
                raise HTTPException(status_code=503, detail="Model not loaded yet")
            try:
                asyncio.create_task(self.run_speak_func(payload.message))
                return {"status": "speaking", "message": payload.message}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/clone_voice")
        async def clone_voice(
            audio_file: UploadFile = File(...),
            name: str = Form("My Cloned Voice"),
        ):
            """Clone a voice from an uploaded audio file"""
            return await self._clone_voice_from_upload(audio_file, name)

        @self.router.post("/use_recorded_voice")
        async def use_recorded_voice():
            """Clone voice from biorecorder's voice_sample.wav"""
            return await self._clone_voice_from_biorecorder()

        @self.router.get("/hf_status")
        async def hf_status():
            """Check if a HuggingFace token is stored and cloning is available."""
            try:
                from huggingface_hub import get_token
                token = get_token()
                has_token = token is not None and len(token) > 0
            except Exception:
                has_token = False

            cloning_available = has_token and self.tts_model is not None and self.voice_state is not None
            # Also check if the cloning model weights exist in cache
            cloning_model_cached = self._check_cloning_model_cached()
            return {
                "has_token": has_token,
                "cloning_model_cached": cloning_model_cached,
                "cloning_available": cloning_available or cloning_model_cached,
            }

        @self.router.post("/hf_login")
        async def hf_login(payload: HfLoginPayload):
            """
            Authenticate with HuggingFace using a user-provided token.
            On success, reloads the model so cloning weights are downloaded.
            """
            token = payload.token.strip()
            if not token:
                raise HTTPException(status_code=400, detail="Token cannot be empty")
            try:
                from huggingface_hub import login as hf_login_fn
                hf_login_fn(token=token, add_to_git_credential=False)
                self.logger.info("HuggingFace authentication successful")
            except Exception as e:
                self.logger.error(f"HuggingFace login failed: {e}")
                raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

            # Reload model in background — this time cloning weights will be downloaded
            self.tts_model = None
            self.voice_state = None
            self.ready = False
            model_thread = threading.Thread(target=self._load_model_threaded, daemon=True)
            model_thread.start()
            return {"status": "authenticated", "message": "Model reloading with voice cloning support…"}

    # ── Custom voices management ────────────────────────────────────────

    def _get_voices_dir(self):
        """Return the directory where cloned voices are stored"""
        voices_dir = os.path.join(self.plugin_folder, "voices")
        os.makedirs(voices_dir, exist_ok=True)
        return voices_dir

    def _get_custom_voices(self):
        """List custom (cloned) voice files"""
        voices_dir = self._get_voices_dir()
        custom = []
        for f in os.listdir(voices_dir):
            if f.endswith(".safetensors"):
                label = os.path.splitext(f)[0].replace("_", " ").title()
                custom.append({
                    "name": f,
                    "label": f"🎤 {label} (Cloned)",
                    "path": os.path.join(voices_dir, f),
                    "is_custom": True,
                })
        return custom

    def _check_cloning_model_cached(self):
        """Check if pocket-tts voice-cloning weights exist in HuggingFace cache."""
        try:
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
            cloning_model_dir = os.path.join(cache_dir, "models--kyutai--pocket-tts")
            if not os.path.isdir(cloning_model_dir):
                return False
            # The cloning model has a significantly larger blob than the no-cloning one
            blobs_dir = os.path.join(cloning_model_dir, "blobs")
            if not os.path.isdir(blobs_dir):
                return False
            for fname in os.listdir(blobs_dir):
                fpath = os.path.join(blobs_dir, fname)
                if os.path.isfile(fpath) and os.path.getsize(fpath) > 50 * 1024 * 1024:
                    return True
            return False
        except Exception:
            return False

    # ── Model loading ───────────────────────────────────────────────────

    def _load_model_threaded(self):
        """Load the pocket-tts model in a background thread.
        Called from startup() to avoid blocking the event loop."""
        try:
            from pocket_tts import TTSModel

            self._model_loading = True
            language = self._resolve_language()
            use_24l = self.settings.get("use_24l", False)
            temp = self.settings.get("temp", 0.7)
            eos_threshold = self.settings.get("eos_threshold", -4.0)

            # Some languages ONLY have a 24L model (French, Portuguese, Spanish).
            # The _24l suffix is passed as the `language` arg directly (e.g. "french_24l").
            # `config` is only for custom .yaml config file paths — do NOT use it here.
            must_use_24l = language in REQUIRES_24L

            if must_use_24l:
                # French, Portuguese, Spanish require the 24L variant
                tts_language = f"{language}_24l"
                self.logger.info(f"Language '{language}' requires 24L — loading as language='{tts_language}'")
            elif use_24l and language != "english":
                # User opted into optional 24L
                tts_language = f"{language}_24l"
            else:
                tts_language = language

            self.logger.info(
                f"Loading pocket-tts model: language={tts_language}, temp={temp}, eos={eos_threshold}"
            )

            start = time.time()
            self.tts_model = TTSModel.load_model(
                language=tts_language,
                temp=temp,
                eos_threshold=eos_threshold,
            )


            elapsed = time.time() - start
            self.model_language = language
            self.logger.info(f"Pocket-tts model loaded in {elapsed:.1f}s")

            # Load voice state
            self._load_voice_state()

            self.is_loaded = True
            self._model_loading = False
            self.mark_ready()
            self.logger.info("Pocket TTS is ready")

        except Exception as e:
            self._model_loading = False
            self.logger.error(f"Failed to load pocket-tts model: {e}", exc_info=True)

    def _load_voice_state(self):
        """Load the voice state (built-in or custom) based on current settings."""
        if self.tts_model is None:
            return

        voice = self.settings.get("voice", "auto")
        language = self.model_language or self._resolve_language()

        try:
            if voice == "auto":
                # Auto-select default voice for current language
                voice_name = DEFAULT_VOICE.get(language, "alba")
                self.logger.info(f"Auto-selecting voice '{voice_name}' for language '{language}'")
                self.voice_state = self.tts_model.get_state_for_audio_prompt(voice_name)

            elif voice == "custom":
                # Load custom voice from safetensors or wav path
                custom_path = self.settings.get("custom_voice_path", "")
                if custom_path and os.path.exists(custom_path):
                    self.logger.info(f"Loading custom voice from: {custom_path}")
                    self.voice_state = self.tts_model.get_state_for_audio_prompt(custom_path)
                else:
                    self.logger.warning(f"Custom voice path not found: {custom_path}, falling back to auto")
                    voice_name = DEFAULT_VOICE.get(language, "alba")
                    self.voice_state = self.tts_model.get_state_for_audio_prompt(voice_name)

            else:
                # Specific built-in voice name (e.g. "estelle")
                self.logger.info(f"Loading built-in voice: {voice}")
                self.voice_state = self.tts_model.get_state_for_audio_prompt(voice)

            self.logger.info("Voice state loaded successfully")

        except Exception as e:
            self.logger.error(f"Error loading voice state: {e}", exc_info=True)
            # Fallback to default voice
            try:
                voice_name = DEFAULT_VOICE.get(language, "alba")
                self.logger.info(f"Fallback: loading default voice '{voice_name}'")
                self.voice_state = self.tts_model.get_state_for_audio_prompt(voice_name)
            except Exception as e2:
                self.logger.error(f"Even fallback voice failed: {e2}")
                self.voice_state = None

    # ── Voice cloning ───────────────────────────────────────────────────

    async def _clone_voice_from_upload(self, audio_file: UploadFile, name: str):
        """Clone a voice from an uploaded audio file"""
        from pocket_tts import export_model_state

        if self.tts_model is None:
            raise HTTPException(status_code=503, detail="Model not loaded yet")

        try:
            audio_bytes = await audio_file.read()
            if not audio_bytes:
                raise HTTPException(status_code=400, detail="Empty audio file")

            # Save uploaded file temporarily
            voices_dir = self._get_voices_dir()
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
            temp_wav = os.path.join(voices_dir, f"_temp_{safe_name}.wav")
            with open(temp_wav, "wb") as f:
                f.write(audio_bytes)

            # Generate voice state from audio (CPU-bound, run in thread)
            def _clone():
                voice_state = self.tts_model.get_state_for_audio_prompt(temp_wav)
                # Export to safetensors for fast reload
                safetensors_path = os.path.join(voices_dir, f"{safe_name}.safetensors")
                export_model_state(voice_state, safetensors_path)
                return voice_state, safetensors_path

            voice_state, safetensors_path = await asyncio.to_thread(_clone)

            # Clean up temp wav
            try:
                os.remove(temp_wav)
            except OSError:
                pass

            # Update active voice state and settings
            self.voice_state = voice_state
            self.update_my_settings("voice", "custom")
            self.update_my_settings("custom_voice_path", safetensors_path)
            self.settings = self.get_my_settings()

            self.logger.info(f"Voice cloned successfully: {name} -> {safetensors_path}")
            return {
                "status": "cloned",
                "name": name,
                "path": safetensors_path,
            }

        except HTTPException:
            raise
        except ValueError as e:
            err_str = str(e)
            if "voice cloning" in err_str.lower() or "VOICE_CLONING_UNSUPPORTED" in err_str:
                self.logger.warning("Voice cloning unavailable: HuggingFace login required")
                raise HTTPException(status_code=403, detail=HF_CLONING_INSTRUCTIONS)
            self.logger.error(f"Error cloning voice: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to clone voice: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error cloning voice: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to clone voice: {str(e)}")

    async def _clone_voice_from_biorecorder(self):
        """Clone voice from biorecorder's existing voice_sample.wav"""
        from pocket_tts import export_model_state

        if self.tts_model is None:
            raise HTTPException(status_code=503, detail="Model not loaded yet")

        try:
            # Fetch voice sample from biorecorder plugin
            bio_voice_path = os.path.join(
                self.appdata_path, self.app_name, "plugins", "biorecorder", "voice_sample.wav"
            )

            if not os.path.exists(bio_voice_path):
                raise HTTPException(
                    status_code=404,
                    detail="No voice sample found. Please complete the biorecorder first."
                )

            voices_dir = self._get_voices_dir()
            name = f"my_voice_{time.strftime('%Y%m%d_%H%M')}"

            # Generate voice state from biorecorder audio (CPU-bound)
            def _clone():
                voice_state = self.tts_model.get_state_for_audio_prompt(bio_voice_path)
                safetensors_path = os.path.join(voices_dir, f"{name}.safetensors")
                export_model_state(voice_state, safetensors_path)
                return voice_state, safetensors_path

            voice_state, safetensors_path = await asyncio.to_thread(_clone)

            # Update active voice state and settings
            self.voice_state = voice_state
            self.update_my_settings("voice", "custom")
            self.update_my_settings("custom_voice_path", safetensors_path)
            self.settings = self.get_my_settings()

            self.logger.info(f"Voice cloned from biorecorder: {safetensors_path}")
            return {
                "status": "cloned",
                "name": name,
                "path": safetensors_path,
            }

        except HTTPException:
            raise
        except ValueError as e:
            err_str = str(e)
            if "voice cloning" in err_str.lower() or "VOICE_CLONING_UNSUPPORTED" in err_str:
                self.logger.warning("Voice cloning unavailable: HuggingFace login required")
                raise HTTPException(status_code=403, detail=HF_CLONING_INSTRUCTIONS)
            self.logger.error(f"Error cloning from biorecorder: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to clone voice: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error cloning from biorecorder: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to clone voice: {str(e)}")

    # ── Hooks ───────────────────────────────────────────────────────────

    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

        self.settings = self.get_my_settings()

        # Load model in background thread (like asrvosk pattern)
        model_thread = threading.Thread(target=self._load_model_threaded, daemon=True)
        model_thread.start()
        self.logger.info("Pocket TTS model loading started in background thread")

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        """Called when plugin settings are updated via settings UI"""
        if plugin_name != self.plugin_name:
            return

        old_settings = self.settings.copy() if self.settings else {}
        self.settings = self.get_my_settings()

        # Check if language-affecting settings changed (requires model reload)
        old_lang = old_settings.get("use_24l", False)
        new_lang = self.settings.get("use_24l", False)
        if old_lang != new_lang:
            self.logger.info("Model config changed, reloading model...")
            model_thread = threading.Thread(target=self._load_model_threaded, daemon=True)
            model_thread.start()
        else:
            # Just voice change — reload voice state only
            old_voice = old_settings.get("voice", "auto")
            new_voice = self.settings.get("voice", "auto")
            if old_voice != new_voice or old_settings.get("custom_voice_path") != self.settings.get("custom_voice_path"):
                self._load_voice_state()

    @hookimpl
    def global_settings_updated(self):
        """Called when global settings (language etc.) change"""
        old_language = self.model_language
        self.settings = self.get_my_settings()
        new_language = self._resolve_language()

        if new_language != old_language:
            self.logger.info(f"Language changed from {old_language} to {new_language}, reloading model...")
            model_thread = threading.Thread(target=self._load_model_threaded, daemon=True)
            model_thread.start()

    @hookimpl
    def speak(self, message):
        if self.is_loaded and self.voice_state is not None:
            self.logger.info(f"§§§§ POCKETTTS SPEAKING: {message}")
            asyncio.create_task(self.run_speak_func_with_translation(message))

    @hookimpl
    def test_speak(self, message, **kwargs):
        voice = kwargs.get('voice', None)
        self.logger.info(f"TEST SPEAK: message={message}, voice={voice}")
        asyncio.create_task(self.run_speak_func(message))

    # ── Speech pipeline ─────────────────────────────────────────────────

    def run_restart_asr(self):
        asyncio.create_task(self.restart_asr())

    async def restart_asr(self):
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func(self, message):
        await self.pm.trigger_hook(hook_name="pause_asr")
        await asyncio.sleep(0.1)  # Ensure pause message reaches frontend
        success = await self.speak_func(message)
        if not success:
            self.logger.warning("speak_func failed, triggering speak_fallback")
            await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
        await self.pm.trigger_hook(hook_name="restart_asr")

    async def run_speak_func_with_translation(self, message):
        """Translate outgoing speech before speaking"""
        translated_message = await self.translate_for_interlocutor(message, direction="outgoing")
        await self.run_speak_func(translated_message)

    async def speak_func(self, message):
        """Generate audio from text using pocket-tts and play it via sounddevice."""
        self.logger.info(f"SPEAK FUNC: {message}")
        try:
            if self.tts_model is None or self.voice_state is None:
                self.logger.error("Cannot speak: model or voice not loaded")
                return False

            # Generate audio in a thread (CPU-bound operation)
            def _generate():
                audio_tensor = self.tts_model.generate_audio(
                    self.voice_state, message
                )
                return audio_tensor

            audio_tensor = await asyncio.to_thread(_generate)

            if audio_tensor is None:
                self.logger.error("generate_audio returned None")
                return False

            # Convert torch tensor to numpy for playback
            import torch
            if isinstance(audio_tensor, torch.Tensor):
                audio_np = audio_tensor.cpu().numpy()
            else:
                audio_np = np.array(audio_tensor)

            # Ensure 1D
            if audio_np.ndim > 1:
                audio_np = audio_np.squeeze()

            sample_rate = self.tts_model.sample_rate

            # Normalize to int16 range for sounddevice
            if audio_np.dtype == np.float32 or audio_np.dtype == np.float64:
                # Clamp to [-1, 1] then scale
                audio_np = np.clip(audio_np, -1.0, 1.0)
                audio_int16 = (audio_np * 32767).astype(np.int16)
            else:
                audio_int16 = audio_np.astype(np.int16)

            self.logger.info(
                f"Playing audio: {len(audio_int16)} samples at {sample_rate}Hz "
                f"({len(audio_int16)/sample_rate:.1f}s)"
            )

            # Play audio synchronously in thread
            def _play():
                sd.play(audio_int16, samplerate=sample_rate)
                sd.wait()

            await asyncio.to_thread(_play)
            self.logger.info("Playback finished")
            return True

        except Exception as e:
            self.logger.error(f"Error in speak_func: {e}", exc_info=True)
            return False

    # ── Incoming messages ───────────────────────────────────────────────

    def process_incoming_message(self, message):
        """Handle messages from the frontend WebSocket"""
        try:
            data = message
            if isinstance(message, (bytes, bytearray)):
                try:
                    data = message.decode('utf-8')
                except Exception:
                    data = message

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    pass

            if isinstance(data, dict) and 'action' in data:
                if data.get('action') == 'test_speak':
                    msg = data.get('message', 'Hello, how are you doing?')
                    asyncio.create_task(self.run_speak_func(msg))
                    return
                elif data.get('action') == 'get_voices':
                    language = self._resolve_language()
                    voices = BUILTIN_VOICES.get(language, [])
                    custom = self._get_custom_voices()
                    self.send_message_to_frontend({
                        "type": "voice_list",
                        "builtin": voices,
                        "custom": custom,
                        "language": language,
                    }, plugin_name='pocketttsSettings')
                    return

            super().process_incoming_message(message)
        except Exception as e:
            self.logger.error(f"Error processing incoming message: {e}")
