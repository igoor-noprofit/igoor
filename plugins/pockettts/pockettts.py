from plugin_manager import hookimpl
from plugins.baseplugin.baseplugin import Baseplugin
from settings_manager import SettingsManager
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi import Form
from pydantic import BaseModel
from typing import Optional
import asyncio
import os
import sys
import threading
import time
import json
import uuid
import numpy as np
import sounddevice as sd

from websocket_server import websocket_server

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
#
# License note (IGOOR is AGPLv3): only voices whose source recordings are
# AGPLv3-compatible are listed. Excluded for license incompatibility:
#   - cosette (expresso/, CC BY-NC 4.0 — non-commercial)
#   - jean    (ears/,      CC BY-NC 4.0 — non-commercial)
#   - rafael  (kyutai/pocket-tts — license unverified, excluded conservatively)
# Remaining voices are CC0 or CC BY 4.0 (attribution), both AGPLv3-compatible.
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
        {"name": "marius", "label": "Marius"},
        {"name": "javert", "label": "Javert"},
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
    # portuguese: no AGPLv3-compatible preset voice available (rafael excluded).
    # 'auto' for Portuguese falls back to DEFAULT_VOICE → "alba" (cross-language).
    "portuguese": [],
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

# Default voice per language (first voice in each list). Portuguese has no
# AGPLv3-compatible preset, so it's omitted and auto-falls back to "alba"
# (voices are cross-language — see note above BUILTIN_VOICES).
DEFAULT_VOICE = {
    "english": "alba",
    "french": "estelle",
    "italian": "giovanni",
    "german": "juergen",
    "spanish": "lola",
}

# Languages that ONLY have a 24-layer model (no standard variant available).
# Verified from pocket_tts/config/ directory — only french has no standard .yaml.
# Portuguese, Spanish, German, Italian all have both standard and _24l variants.
REQUIRES_24L = {"french"}

# ── Google Drive model download ─────────────────────────────────────────
# The model weights are gated on HuggingFace (kyutai/pocket-tts). To avoid
# forcing users to create an HF account, we mirror the weights on public
# Google Drive folders (one per language variant) and download only the
# currently-selected language. The folders mirror the gated repo (they
# include voice-cloning weights).
#
# The variant → folder-URL mapping lives in plugins/pockettts/models.csv
# (kept out of the source so it can be updated without touching code). Each
# row is: <variant>,<https://drive.google.com/drive/folders/<id>>. A variant
# absent from the CSV falls back to the public HF without-voice-cloning repo.
MODELS_CSV = os.path.join(os.path.dirname(__file__), "models.csv")


def _load_gdrive_models():
    """Parse models.csv into {variant: folder_url}. Returns {} on any failure.
    Lines whose first field starts with '#' are comments."""
    mapping = {}
    try:
        import csv
        with open(MODELS_CSV, newline="") as f:
            for row in csv.DictReader(f):
                variant = (row.get("model") or "").strip()
                url = (row.get("url") or "").strip()
                if not variant or variant.startswith("#") or not url:
                    continue
                mapping[variant] = url
    except Exception:
        pass
    return mapping


GDRIVE_MODELS = _load_gdrive_models()


class TestSpeakPayload(BaseModel):
    message: str = "Hello, how are you doing? I feel better today!"
    # Optional voice selection from the settings dropdown, so "Test voice"
    # tests what is SELECTED (not yet saved) rather than the last saved
    # voice. Raw dropdown value: 'auto', a built-in name, or 'custom:<file>'.
    voice: Optional[str] = None


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
        # When the model is loaded from local Drive-downloaded weights, this holds
        # the language dir (containing model.safetensors + embeddings/). Used to
        # resolve built-in voice names to local .safetensors paths, since the
        # pocket-tts library rejects predefined voice names for non-CONFIGS origins.
        self._local_lang_dir = None

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
            """Test speech synthesis. When a voice selection is provided it is
            used for this test only (the saved settings are untouched), so the
            button tests what the user selected in the dropdown. The request
            completes only after playback ends, letting the settings UI keep
            the Test button disabled for the whole test."""
            if self.tts_model is None or self.voice_state is None:
                raise HTTPException(status_code=503, detail="Model not loaded yet")
            try:
                state = self._state_for_test(payload.voice)
                if state is None:
                    raise HTTPException(
                        status_code=400, detail=f"Voice not available: {payload.voice}"
                    )
                success = await self.run_speak_func(payload.message, voice_state=state)
                if not success:
                    raise HTTPException(status_code=500, detail="Test speech failed")
                return {"status": "done", "message": payload.message}
            except HTTPException:
                raise
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

    # ── Google Drive model download ───────────────────────────────────────

    def _get_models_dir(self):
        """Local folder where per-language Drive-downloaded weights live."""
        models_dir = os.path.join(self.plugin_folder, "models")
        os.makedirs(models_dir, exist_ok=True)
        return models_dir

    def _resolve_drive_folder(self, tts_language):
        """Return the Google Drive folder URL for a (already 24L-suffixed) pocket-tts
        variant, or None if it isn't listed in models.csv."""
        return GDRIVE_MODELS.get(tts_language)

    def _ensure_lang_downloaded(self, tts_language):
        """Download the Drive folder for `tts_language` and locate the model +
        tokenizer files inside it.

        Returns ({"model": <path>, "tokenizer": <path>}, lang_dir) on success, or
        (None, None) if the variant isn't on Drive or the download fails (caller
        falls back to HF). Idempotent: gdown resume= skips files already present.
        """
        lang_dir = os.path.join(self._get_models_dir(), tts_language)
        os.makedirs(lang_dir, exist_ok=True)

        # The folder contains model.safetensors + tokenizer.model at its root
        # (plus an embeddings/ subdir of preset voices).
        local_files = {
            "model": os.path.join(lang_dir, "model.safetensors"),
            "tokenizer": os.path.join(lang_dir, "tokenizer.model"),
        }
        missing = [k for k, p in local_files.items()
                   if not (os.path.isfile(p) and os.path.getsize(p) > 0)]

        if not missing:
            # Never re-query Drive when the files are already on disk: the
            # folder listing itself fails often enough (rate limits) that it
            # would discard a perfectly good local model.
            return local_files, lang_dir

        folder_url = self._resolve_drive_folder(tts_language)
        if folder_url is None:
            return None, None

        import gdown

        try:
            self.logger.info(f"Downloading '{tts_language}' from Google Drive → {lang_dir}")
            # resume=True skips already-downloaded files (idempotent reloads).
            gdown.download_folder(url=folder_url, output=lang_dir, quiet=False, resume=True)
        except Exception as e:
            self.logger.warning(
                f"Drive download failed for '{tts_language}', falling back to HuggingFace: {e}"
            )
            return None, None

        missing = [k for k, p in local_files.items()
                   if not (os.path.isfile(p) and os.path.getsize(p) > 0)]
        if missing:
            self.logger.warning(
                f"Drive folder for '{tts_language}' missing required files {missing}; "
                f"falling back to HuggingFace"
            )
            return None, None
        self.logger.info(f"'{tts_language}' available locally from Google Drive")
        return local_files, lang_dir

    def _write_local_config_yaml(self, tts_language, local_files):
        """Clone the library's bundled config for `tts_language`, override the two
        weight/tokenizer paths to point at the local Drive-downloaded files, and
        write it next to them. Returns the path to the generated YAML.

        Only these two keys are changed so the config still validates under the
        library's StrictModel (extra='forbid').
        """
        import yaml
        from pocket_tts.utils.config import CONFIGS_DIR

        src = CONFIGS_DIR / f"{tts_language}.yaml"
        with open(src, "r") as f:
            cfg = yaml.safe_load(f)
        cfg["weights_path"] = local_files["model"]
        cfg["flow_lm"]["lookup_table"]["tokenizer_path"] = local_files["tokenizer"]

        out_path = os.path.join(self._get_models_dir(), tts_language, "local_config.yaml")
        with open(out_path, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)
        return out_path

    # ── Model loading ───────────────────────────────────────────────────

    @staticmethod
    def _defuse_speechbrain_lazy_import():
        """pocket-tts >= 3 pulls torch.distributed.tensor, whose import makes
        torch call inspect.get_source -> inspect.getmodule, which scans
        sys.modules with hasattr(module, ...). Speechbrain's lazy module
        proxies react by eagerly importing their target — and proxies for
        optional dependencies (k2_fsa, nlp, ...) raise ImportError, killing
        our import. Upstream guards against the inspect-triggered case but
        checks endswith('/inspect.py'), which never matches Windows paths.
        Make missing optional proxies behave as missing attributes instead."""
        from speechbrain.utils.importutils import LazyModule
        if getattr(LazyModule.ensure_module, "_igoor_patched", False):
            return
        original = LazyModule.ensure_module

        def ensure_module(self, stacklevel=1):
            try:
                return original(self, stacklevel)
            except ImportError:
                raise AttributeError(
                    f"optional speechbrain module not importable: {self.target}"
                )

        ensure_module._igoor_patched = True
        LazyModule.ensure_module = ensure_module

    def _load_model_threaded(self):
        """Load the pocket-tts model in a background thread.
        Called from startup() to avoid blocking the event loop."""
        try:
            if "speechbrain" in sys.modules:
                self._defuse_speechbrain_lazy_import()
            from pocket_tts import TTSModel

            self._model_loading = True
            language = self._resolve_language()
            use_24l = self.settings.get("use_24l", False)
            temp = float(self.settings.get("temp", 0.7))
            eos_threshold = float(self.settings.get("eos_threshold", -4.0))

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
            elif language == "english" and self.settings.get("use_2026_04", True):
                # Upstream's dated checkpoint, recommended for short sentences
                # and voice cloning (IGOOR's main use case). Mirrored on Drive.
                tts_language = "english_2026-04"
                self.logger.info("English: using the 2026-04 checkpoint")
            else:
                tts_language = language

            # int8 dynamic quantization: ~30% faster on CPU (lib >= 2.0)
            quantize = bool(self.settings.get("quantize", True))

            self.logger.info(
                f"Loading pocket-tts model: language={tts_language}, temp={temp}, "
                f"eos={eos_threshold}, quantize={quantize}"
            )

            start = time.time()
            # Prefer locally-downloaded Drive weights (no HF account needed);
            # fall back to the library's HF download path if Drive isn't
            # configured for this language or the download failed.
            local_files, lang_dir = self._ensure_lang_downloaded(tts_language)
            if local_files is not None:
                config_path = self._write_local_config_yaml(tts_language, local_files)
                self.logger.info(f"Loading pocket-tts from local Google Drive weights: {config_path}")
                self.tts_model = TTSModel.load_model(
                    config=config_path,
                    temp=temp,
                    eos_threshold=eos_threshold,
                    quantize=quantize,
                )
                # Remember the dir so built-in voice names can be resolved to the
                # local embeddings/*.safetensors (the library rejects predefined
                # voice names for non-CONFIGS config origins).
                self._local_lang_dir = lang_dir
            else:
                self.logger.info("Loading pocket-tts from HuggingFace (Drive path unavailable)")
                self.tts_model = TTSModel.load_model(
                    language=tts_language,
                    temp=temp,
                    eos_threshold=eos_threshold,
                    quantize=quantize,
                )
                self._local_lang_dir = None


            elapsed = time.time() - start
            self.model_language = language
            self.logger.info(f"Pocket-tts model loaded in {elapsed:.1f}s")

            # Load voice state
            self._load_voice_state()

            if self.voice_state is None:
                # Without a voice the plugin can speak nothing: report not
                # ready instead of silently no-oping every speak request.
                # This happens when neither Drive weights (local embeddings)
                # nor an HF login for the gated voice repo are available.
                self.is_loaded = False
                self._model_loading = False
                self.mark_not_ready()
                self.logger.error(
                    "Pocket TTS loaded the model but no voice is available "
                    "(no local embeddings and no HuggingFace login)"
                )
                return

            self.is_loaded = True
            self._model_loading = False
            self.mark_ready()
            self.logger.info("Pocket TTS is ready")

        except Exception as e:
            self._model_loading = False
            self.logger.error(f"Failed to load pocket-tts model: {e}", exc_info=True)

    def _resolve_voice_prompt(self, voice_name):
        """Translate a built-in voice NAME into something get_state_for_audio_prompt
        accepts given how the model was loaded.

        pocket-tts rejects predefined voice names unless the model's config origin
        is under its bundled CONFIGS_DIR. When we load from local Drive weights the
        origin is our APPDATA yaml, so that path is unavailable. But the Drive
        folder ships the same voices as local embeddings/*.safetensors — and
        passing a local .safetensors path works regardless of origin. So map the
        name to that file when present; otherwise return the bare name (HF path).
        """
        if self._local_lang_dir:
            local_emb = os.path.join(self._local_lang_dir, "embeddings", f"{voice_name}.safetensors")
            if os.path.isfile(local_emb):
                return local_emb
        return voice_name

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
                self.voice_state = self.tts_model.get_state_for_audio_prompt(
                    self._resolve_voice_prompt(voice_name)
                )

            elif voice == "custom":
                # Load custom voice from safetensors or wav path
                custom_path = self.settings.get("custom_voice_path", "")
                if custom_path and os.path.exists(custom_path):
                    self.logger.info(f"Loading custom voice from: {custom_path}")
                    self.voice_state = self.tts_model.get_state_for_audio_prompt(custom_path)
                else:
                    # Self-heal: settings store an absolute path, which breaks
                    # after importing data on another machine/user. If the same
                    # file name exists in this plugin's voices folder (restored
                    # by the import), adopt it silently.
                    self.logger.warning(f"Custom voice path not found: {custom_path}")
                    basename = os.path.basename(custom_path) if custom_path else ""
                    local_candidate = os.path.join(self._get_voices_dir(), basename) if basename else ""
                    if basename and os.path.isfile(local_candidate):
                        self.logger.info(f"Adopting local voice file with same name: {local_candidate}")
                        self.update_my_settings("custom_voice_path", local_candidate)
                        self.settings = self.get_my_settings()
                        self.voice_state = self.tts_model.get_state_for_audio_prompt(local_candidate)
                    else:
                        voice_name = DEFAULT_VOICE.get(language, "alba")
                        self.voice_state = self.tts_model.get_state_for_audio_prompt(
                            self._resolve_voice_prompt(voice_name)
                        )

            else:
                # Specific built-in voice name (e.g. "estelle")
                self.logger.info(f"Loading built-in voice: {voice}")
                self.voice_state = self.tts_model.get_state_for_audio_prompt(
                    self._resolve_voice_prompt(voice)
                )

            self.logger.info("Voice state loaded successfully")

        except Exception as e:
            self.logger.error(f"Error loading voice state: {e}", exc_info=True)
            # Fallback to default voice
            try:
                voice_name = DEFAULT_VOICE.get(language, "alba")
                self.logger.info(f"Fallback: loading default voice '{voice_name}'")
                self.voice_state = self.tts_model.get_state_for_audio_prompt(
                    self._resolve_voice_prompt(voice_name)
                )
            except Exception as e2:
                self.logger.error(f"Even fallback voice failed: {e2}")
                self.voice_state = None

    # ── Voice cloning ───────────────────────────────────────────────────

    def _state_for_test(self, voice):
        """Build a throwaway voice state for the Test button from the raw
        dropdown selection ('auto', a built-in name, or 'custom:<file>').
        Returns None when the requested voice is not available locally; the
        caller then reports it instead of silently testing another voice."""
        if not voice or voice == "custom":
            # no specific selection (or bare 'custom' without a file) ->
            # test the currently loaded voice
            return self.voice_state
        try:
            if voice == "auto":
                name = DEFAULT_VOICE.get(self._resolve_language(), "alba")
                return self.tts_model.get_state_for_audio_prompt(
                    self._resolve_voice_prompt(name)
                )
            if voice.startswith("custom:"):
                path = os.path.join(self._get_voices_dir(), voice[len("custom:"):])
                if not os.path.isfile(path):
                    return None
                return self.tts_model.get_state_for_audio_prompt(path)
            return self.tts_model.get_state_for_audio_prompt(
                self._resolve_voice_prompt(voice)
            )
        except Exception as e:
            self.logger.warning(f"Could not prepare test voice '{voice}': {e}")
            return None

    def _unique_voice_path(self, voices_dir: str, safe_name: str) -> str:
        """A voice .safetensors cannot be overwritten while its tensors are
        memory-mapped by the loaded voice state (Windows os error 1224), and
        the upload UI names clones by date so same-day clones collide. Always
        write to a fresh, auto-suffixed file instead."""
        base = os.path.join(voices_dir, f"{safe_name}.safetensors")
        if not os.path.exists(base):
            return base
        n = 2
        while os.path.exists(os.path.join(voices_dir, f"{safe_name} ({n}).safetensors")):
            n += 1
        return os.path.join(voices_dir, f"{safe_name} ({n}).safetensors")

    def _prepare_clone_audio(self, audio_bytes: bytes, filename: str, voices_dir: str) -> str:
        """Write the uploaded audio to a temp file the TTS can read and return
        its path. Keeps the ORIGINAL extension (the reader dispatches on it —
        naming everything .wav made every non-WAV upload fail with "file does
        not start with RIFF id"), validates the content is readable audio,
        and transcodes via ffmpeg when the format is not directly supported
        (m4a, mp4, aac, webm). Raises 400 with a clear message otherwise."""
        import soundfile as sf

        ext = os.path.splitext(filename or "")[1].lower()
        if not ext.startswith(".") or not ext[1:].isalnum():
            ext = ".wav"
        temp_path = os.path.join(voices_dir, f"_temp_clone{ext}")
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        try:
            sf.info(temp_path)
            return temp_path
        except Exception:
            pass

        # Not directly readable: transcode via ffmpeg (pydub) if available
        try:
            from pydub import AudioSegment

            wav_path = os.path.join(voices_dir, "_temp_clone.wav")
            AudioSegment.from_file(temp_path).export(wav_path, format="wav")
            os.remove(temp_path)
            sf.info(wav_path)
            return wav_path
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise HTTPException(
                status_code=400,
                detail="Unsupported audio format. Supported: WAV, MP3, FLAC, OGG, M4A, WEBM "
                       "(M4A/WEBM require ffmpeg)",
            )

    async def _clone_voice_from_upload(self, audio_file: UploadFile, name: str):
        """Clone a voice from an uploaded audio file"""
        from pocket_tts import export_model_state

        if self.tts_model is None:
            raise HTTPException(status_code=503, detail="Model not loaded yet")

        try:
            audio_bytes = await audio_file.read()
            if not audio_bytes:
                raise HTTPException(status_code=400, detail="Empty audio file")

            # Save uploaded file temporarily (validated + transcoded if needed)
            voices_dir = self._get_voices_dir()
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
            temp_wav = self._prepare_clone_audio(audio_bytes, audio_file.filename, voices_dir)

            # Generate voice state from audio (CPU-bound, run in thread)
            def _clone():
                voice_state = self.tts_model.get_state_for_audio_prompt(temp_wav)
                # Export to safetensors for fast reload (fresh file: see
                # _unique_voice_path)
                safetensors_path = self._unique_voice_path(voices_dir, safe_name)
                export_model_state(voice_state, safetensors_path)
                return voice_state, safetensors_path

            try:
                voice_state, safetensors_path = await asyncio.to_thread(_clone)
            finally:
                # Remove the temp audio also when cloning fails (a leaked
                # _temp_*.wav used to survive every failed clone attempt)
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
                safetensors_path = self._unique_voice_path(voices_dir, name)
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

    @hookimpl
    def tts_playback_finished(self):
        """Releases wait_playback_finished after the browser acked playback,
        so ASR restarts immediately instead of after the 30s timeout."""
        self._on_playback_finished()

    # ── Speech pipeline ─────────────────────────────────────────────────

    def run_restart_asr(self, force_ready=False):
        asyncio.create_task(self.restart_asr(force_ready=force_ready))

    async def restart_asr(self, force_ready=False):
        # force_ready is required by asrjs's hookimpl; omitting it raises a
        # HookCallError that can take down the ASGI serving loop.
        await self.pm.trigger_hook(hook_name="restart_asr", force_ready=force_ready)

    async def run_speak_func(self, message, voice_state=None):
        await self.pm.trigger_hook(hook_name="pause_asr")
        await asyncio.sleep(0.1)  # Ensure pause message reaches frontend
        success = await self.speak_func(message, voice_state=voice_state)
        if not success:
            self.logger.warning("speak_func failed, triggering speak_fallback")
            await self.pm.trigger_hook(hook_name="speak_fallback", message=message)
        # force_ready is required by asrjs's hookimpl; omitting it raises a
        # HookCallError that can take down the ASGI serving loop.
        await self.pm.trigger_hook(hook_name="restart_asr", force_ready=False)

    async def run_speak_func_with_translation(self, message):
        """Translate outgoing speech before speaking"""
        translated_message = await self.translate_for_interlocutor(message, direction="outgoing")
        await self.run_speak_func(translated_message)

    async def speak_func(self, message, voice_state=None):
        """Generate audio from text: streamed to the browser in CLI mode,
        played via sounddevice otherwise. voice_state lets the Test button
        speak with a selection that isn't saved yet."""
        self.logger.info(f"SPEAK FUNC: {message}")
        try:
            if self.tts_model is None or self.voice_state is None:
                self.logger.error("Cannot speak: model or voice not loaded")
                return False

            if self.is_remote_ui():
                streamed = await self._stream_speech_to_frontend(message, voice_state)
                if not streamed:
                    return await self._speak_local(message, voice_state)
                return True
            return await self._speak_local(message, voice_state)

        except Exception as e:
            self.logger.error(f"Error in speak_func: {e}", exc_info=True)
            return False

    def _pcm16_bytes(self, chunk) -> bytes:
        """Convert a generated audio chunk (torch tensor / array) to int16 PCM."""
        import torch
        if isinstance(chunk, torch.Tensor):
            audio = chunk.detach().cpu().numpy()
        else:
            audio = np.asarray(chunk)
        audio = np.clip(audio.reshape(-1), -1.0, 1.0)
        return (audio * 32767).astype(np.int16).tobytes()

    # Playback padding: pocket-tts generates speech starting at sample 0
    # with almost no tail, so output warm-up (browser AudioContext, speaker
    # amp power-save) clips the head of very short replies like "Oui".
    PLAYBACK_LEAD_S = 0.15
    PLAYBACK_TAIL_S = 0.10

    def _silence_bytes(self, seconds: float) -> bytes:
        rate = int(self.tts_model.sample_rate)
        return b"\x00" * (int(seconds * rate) * 2)  # int16 mono

    def _iter_speech_chunks(self, message, voice_state=None):
        """Blocking generator: int16 PCM chunks as pocket-tts decodes them
        (generate_audio_stream yields as soon as audio is available)."""
        state = voice_state if voice_state is not None else self.voice_state
        yield self._silence_bytes(self.PLAYBACK_LEAD_S)
        for chunk in self.tts_model.generate_audio_stream(state, message):
            yield self._pcm16_bytes(chunk)
        yield self._silence_bytes(self.PLAYBACK_TAIL_S)

    async def _stream_speech_to_frontend(self, message, voice_state=None) -> bool:
        """Stream PCM chunks to the browser while generation runs. Synthesis
        happens in a worker thread so the event loop stays free; the websocket
        protocol matches Baseplugin.stream_audio_to_frontend (play_stream /
        binary chunks / play_stream_end + playback ack)."""
        if not websocket_server.is_socket_open('app'):
            self.logger.warning("No browser connected on the app websocket: cannot stream audio")
            return False
        if not hasattr(self, "_playback_done"):
            self._playback_done = asyncio.Event()
        self._playback_done.clear()

        stream_id = uuid.uuid4().hex
        await self.send_message_to_app(
            {"play_stream": {"id": stream_id, "mime": f"audio/pcm16;rate={self.tts_model.sample_rate}"}}
        )

        failure = threading.Event()

        def produce():
            started = None
            sent = 0
            try:
                for chunk in self._iter_speech_chunks(message, voice_state):
                    if not websocket_server.send_bytes('app', chunk):
                        failure.set()
                        return
                    if started is None:
                        started = time.time()
                        self.logger.info(f"TTS stream {stream_id}: first chunk sent")
                    sent += 1
                if started is not None:
                    self.logger.info(
                        f"TTS stream {stream_id}: last chunk sent ({sent} chunks, "
                        f"{time.time() - started:.2f}s of streaming)"
                    )
            except Exception as e:
                self.logger.error(f"TTS streaming failed: {e}", exc_info=True)
                failure.set()

        producer = threading.Thread(target=produce, daemon=True)
        producer.start()
        while producer.is_alive():
            await asyncio.sleep(0.1)
        await self.send_message_to_app(
            {"play_stream_end": {"id": stream_id, "aborted": failure.is_set()}}
        )
        if failure.is_set():
            return False
        await self.wait_playback_finished(timeout=30)
        return True

    async def _speak_local(self, message, voice_state=None) -> bool:
        """Whole-clip generation and local playback via sounddevice."""

        # Generate audio in a thread (CPU-bound operation)
        def _generate():
            state = voice_state if voice_state is not None else self.voice_state
            audio_tensor = self.tts_model.generate_audio(
                state, message
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

        # Same head/tail padding as the streaming path: output warm-up
        # clips speech that starts at sample 0 (e.g. "Oui")
        pad_lead = np.zeros(int(self.PLAYBACK_LEAD_S * sample_rate), dtype=np.int16)
        pad_tail = np.zeros(int(self.PLAYBACK_TAIL_S * sample_rate), dtype=np.int16)
        audio_int16 = np.concatenate([pad_lead, audio_int16, pad_tail])

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
