"""Self-contained ONNX runtime for the Audio8 TTS 0.1B INT8 model.

Vendored and adapted from the Apache-2.0 Audio8_TTS project
(https://github.com/Audio8-AI/Audio8_TTS, onnx_runtime/arktts_runtime):
the prompt builder, voice store, samplers and the fast-AR/codec interfaces
are reused; the slow-AR adapter implements the 0.1B interface (per-token
step, stacked KV caches + Mamba conv/ssm states, relative semantic logits),
which the published runtime (0.6B-INT4) does not support. The fixed voice
prefix is prefilled once per voice and its state cached, cutting per-utterance
latency roughly in half (verified bit-identical to a cold full prefill).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import threading
import unicodedata
from collections.abc import Iterator
from math import gcd
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf
from scipy.signal import resample_poly
from tokenizers import Tokenizer

# ── text normalization (from arktts_runtime.prompt) ─────────────────────────

_CJK_RANGES = (
    "\u1100-\u11ff\u2e80-\u2fdf\u3000-\u303f\u3040-\u30ff\u3100-\u31ff"
    "\u3400-\u4dbf\u4e00-\u9fff\ua960-\ua97f\uac00-\ud7a3\ud7b0-\ud7ff\uf900-\ufaff"
    "\ufe30-\ufe4f\uff01-\uff9f\U00020000-\U0002fa1f"
)
_CJK_CHARACTER_RE = re.compile(rf"[{_CJK_RANGES}]")
_LINE_BREAK_RE = re.compile(r"[\r\n\v\f\x1c-\x1e\x85\u2028\u2029]")


def _normalize_whitespace(text: str) -> str:
    def replace(match: "re.Match[str]") -> str:
        left = text[match.start() - 1] if match.start() else ""
        right = text[match.end()] if match.end() < len(text) else ""
        if (
            _LINE_BREAK_RE.search(match.group())
            and _CJK_CHARACTER_RE.fullmatch(left)
            and _CJK_CHARACTER_RE.fullmatch(right)
        ):
            return ""
        return " "

    return re.sub(r"\s+", replace, text).strip()


def clean_text(text: str) -> str:
    value = "".join(
        char if char.isspace() else "" if unicodedata.category(char).startswith("C") else char
        for char in str(text)
    )
    return _normalize_whitespace(value)


def format_reference_text(text: str) -> str:
    text = clean_text(text)
    return text if re.search(r"<\|speaker:\d+\|>", text) else f"<|speaker:0|>{text}"


# ── sampling (from arktts_runtime.runtime) ──────────────────────────────────

def _sample(logits: np.ndarray, temperature: float, top_p: float, top_k: int, rng) -> int:
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    order = np.argsort(values)[::-1]
    sorted_values = values[order]
    base = np.exp(sorted_values - np.max(sorted_values))
    base /= base.sum()
    cumulative = np.cumsum(base)
    remove = (cumulative > float(top_p)) | (np.arange(base.size) >= int(top_k))
    remove[0] = False
    masked = values.copy()
    masked[order[remove]] = -np.inf
    scaled = masked / max(float(temperature), 1e-5)
    scaled -= np.max(scaled)
    probs = np.exp(scaled)
    probs /= probs.sum()
    noise = -np.log(np.clip(rng.random(probs.size), 1e-12, 1.0))
    return int(np.argmax(probs / noise))


def _session(path: Path, threads: int | None = None) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.log_severity_level = 3
    if threads is not None:
        options.intra_op_num_threads = int(threads)
        options.inter_op_num_threads = max(1, int(threads) // 2)
    return ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])


# ── voice store (from arktts_runtime.voices) ────────────────────────────────

class VoiceStore:
    def __init__(self, root: Path, num_codebooks: int):
        self.root = Path(root).resolve()
        self.num_codebooks = int(num_codebooks)

    def list(self) -> list[dict]:
        voices = []
        if not self.root.exists():
            return voices
        for meta_path in sorted(self.root.glob("*/meta.json")):
            try:
                voices.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return voices

    def load(self, name: str) -> tuple[np.ndarray, dict]:
        if not name or Path(name).name != name:
            raise ValueError("invalid voice name")
        voice_dir = self.root / name
        meta_path = voice_dir / "meta.json"
        codes_path = voice_dir / "codes.npy"
        if not meta_path.is_file() or not codes_path.is_file():
            raise KeyError(f"voice not found: {name}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        codes = np.load(codes_path, allow_pickle=False).astype(np.int64, copy=False)
        if codes.ndim != 2 or codes.shape[0] != self.num_codebooks or codes.shape[1] == 0:
            raise ValueError(f"invalid codes for voice {name}: {codes.shape}")
        reference_text = str(meta.get("reference_text", "")).strip()
        if not reference_text:
            raise ValueError(f"voice {name} has no reference_text")
        return codes, meta


# ── runtime ──────────────────────────────────────────────────────────────────

class Audio8Runtime:
    """0.1B INT8 inference with per-voice prefix-state caching."""

    def __init__(self, model_dir: Path, voices_dir: Path, threads: int | None = 5):
        self.model_dir = Path(model_dir).resolve()
        self.manifest = json.loads((self.model_dir / "runtime_manifest.json").read_text())
        self.threads = threads
        self.sample_rate = int(self.manifest["sample_rate"])
        self.slow = _session(self.model_dir / self.manifest["slow_decode_model"], threads)
        self.fast = _session(self.model_dir / self.manifest["fast_model"], threads)
        self.decoder = _session(
            self.model_dir / self.manifest["codec_models"][self.manifest["default_codec_precision"]],
            threads,
        )
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer" / "tokenizer.json"))
        self.semantic_begin_id = int(self.manifest["semantic_begin_id"])
        self.num_codebooks = int(self.manifest["num_codebooks"])
        self.voices = VoiceStore(voices_dir, self.num_codebooks)
        self._slow_input_meta = {i.name: i for i in self.slow.get_inputs()}
        self._num_layers = int(self.manifest["num_layers"])
        self._num_fast_layers = int(self.manifest["num_fast_layers"])
        self._prefix_cache: dict[str, tuple[dict, int]] = {}
        self._cache_lock = threading.Lock()
        self._synth_lock = threading.Lock()
        self._encoder = None

    # ── prompt building (mirrors arktts_runtime.prompt.PromptBuilder) ──

    def _encode_text(self, text: str) -> list[int]:
        return list(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def build_prompt(self, text: str, reference_text: str, reference_codes: np.ndarray):
        """Returns (packed prompt [1, num_codebooks+1, T], fixed prefix boundary)."""
        codes = np.asarray(reference_codes, dtype=np.int64)
        if codes.ndim != 2 or codes.shape[0] != self.num_codebooks or codes.shape[1] == 0:
            raise ValueError(f"reference codes must have shape [{self.num_codebooks}, T>0], got {codes.shape}")
        prefix_parts = [
            "<|im_start|>system\n",
            "convert the provided text to speech reference to the following:\n\nText:\n",
            format_reference_text(reference_text),
            "\n\nSpeech:\n",
        ]
        suffix_parts = [
            "<|im_end|>\n",
            "<|im_start|>user\n",
            clean_text(text),
            "<|im_end|>\n",
            "<|im_start|>assistant\n<|voice|>",
        ]
        prefix = [t for part in prefix_parts for t in self._encode_text(part)]
        suffix = [t for part in suffix_parts for t in self._encode_text(part)]
        semantic_ids = (codes[0] + self.semantic_begin_id).tolist()
        row0 = np.asarray(prefix + semantic_ids + suffix, dtype=np.int64)
        values = np.zeros((self.num_codebooks + 1, row0.size), dtype=np.int64)
        values[0] = row0
        begin = len(prefix)
        values[1:, begin : begin + codes.shape[1]] = codes
        return values[np.newaxis], begin + codes.shape[1]

    # ── slow AR: per-token step with stacked KV + Mamba state ──────────

    def _zero_slow_state(self) -> dict:
        return {
            name: np.zeros(meta.shape, dtype=np.float32)
            for name, meta in self._slow_input_meta.items()
            if name not in ("codes", "position")
        }

    def _slow_step(self, codes_column, position, state):
        feeds = {
            "codes": np.asarray(codes_column, dtype=np.int64),
            "position": np.asarray([position], dtype=np.int64),
            **state,
        }
        logits, hidden, key_delta, value_delta, next_conv, next_ssm = self.slow.run(None, feeds)
        state["cache_keys"][:, :, :, position, :] = key_delta
        state["cache_values"][:, :, :, position, :] = value_delta
        state["conv_states"] = next_conv
        state["ssm_states"] = next_ssm
        return np.asarray(logits)[0, -1], np.asarray(hidden)[:, -1:, :]

    def _prefill(self, prompt, start, end, state):
        """Feed prompt positions [start, end); return (state, logits, hidden)."""
        logits = hidden = None
        for t in range(start, end):
            logits, hidden = self._slow_step(prompt[:, :, t : t + 1], t, state)
        return state, logits, hidden

    # ── fast AR (interface identical to the published runtime) ─────────

    def _zero_fast_caches(self) -> list[np.ndarray]:
        shape = (
            1,
            int(self.manifest["fast_n_local_heads"]),
            self.num_codebooks,
            int(self.manifest["fast_head_dim"]),
        )
        return [np.zeros(shape, dtype=np.float32) for _ in range(2 * self._num_fast_layers)]

    def _fast_step(self, hidden, token_id, use_hidden, position, caches):
        feeds = {
            "slow_hidden": np.asarray(hidden, dtype=np.float32),
            "token_id": np.asarray([[token_id]], dtype=np.int64),
            "use_slow_hidden": np.asarray([use_hidden], dtype=np.bool_),
            "input_pos": np.asarray([position], dtype=np.int64),
        }
        for i in range(self._num_fast_layers):
            feeds[f"cache_key_{i}"] = caches[2 * i]
            feeds[f"cache_value_{i}"] = caches[2 * i + 1]
        outputs = self.fast.run(None, feeds)
        for i in range(self._num_fast_layers):
            caches[2 * i][:, :, position, :] = outputs[1 + 2 * i][:, :, 0, :]
            caches[2 * i + 1][:, :, position, :] = outputs[2 + 2 * i][:, :, 0, :]
        return np.asarray(outputs[0])[0, -1]

    # ── sampling: relative layout, logits = 4096 semantic + 1 EOS ──────

    def _sample_semantic(self, logits, previous, temperature, top_p, top_k, rng):
        values = np.asarray(logits).reshape(-1)
        eos = values.size - 1
        idx = _sample(values, temperature, top_p, top_k, rng)
        if idx == eos:
            return None
        semantic = self.semantic_begin_id + int(idx)
        if semantic in previous:
            high = _sample(values, 1.0, 0.9, top_k, rng)
            if high != eos:
                semantic = self.semantic_begin_id + int(high)
        return semantic

    # ── prefix cache ────────────────────────────────────────────────────

    def get_prefix_state(self, voice: str) -> tuple[dict, int]:
        """State after prefilling the fixed voice prefix (built once per voice)."""
        with self._cache_lock:
            cached = self._prefix_cache.get(voice)
            if cached is not None:
                return cached
            reference_codes, meta = self.voices.load(voice)
            prompt, boundary = self.build_prompt("unused", meta["reference_text"], reference_codes)
            state = self._prefill(prompt, 0, boundary, self._zero_slow_state())[0]
            cached = (state, boundary)
            self._prefix_cache[voice] = cached
            return cached

    def drop_prefix_cache(self, voice: str | None = None):
        with self._cache_lock:
            if voice is None:
                self._prefix_cache.clear()
            else:
                self._prefix_cache.pop(voice, None)

    # ── generation ──────────────────────────────────────────────────────

    def iter_codes(
        self,
        text: str,
        voice: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        seed: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> Iterator[np.ndarray]:
        prefix_state, boundary = self.get_prefix_state(voice)
        reference_codes, meta = self.voices.load(voice)
        prompt, _ = self.build_prompt(text, meta["reference_text"], reference_codes)
        prompt_len = int(prompt.shape[2])
        max_seq_len = int(self.manifest["max_seq_len"])
        if prompt_len >= max_seq_len:
            raise ValueError(f"prompt length {prompt_len} exceeds max sequence length {max_seq_len}")
        max_new_tokens = min(int(max_new_tokens), max_seq_len - prompt_len)
        rng = np.random.default_rng(seed)

        state = {k: v.copy() for k, v in prefix_state.items()}
        _, logits, hidden = self._prefill(prompt, boundary, prompt_len, state)

        previous: list[int] = []
        codebook_size = int(self.manifest["codebook_size"])
        for step in range(max_new_tokens):
            if stop_event is not None and stop_event.is_set():
                return
            semantic = self._sample_semantic(logits, previous, temperature, top_p, top_k, rng)
            if semantic is None:
                return
            previous.append(semantic)
            previous = previous[-10:]
            fast_caches = self._zero_fast_caches()
            self._fast_step(hidden, 0, True, 0, fast_caches)
            token = min(max(semantic - self.semantic_begin_id, 0), codebook_size - 1)
            codebooks = [token]
            for fast_pos in range(1, self.num_codebooks):
                fast_logits = self._fast_step(hidden, token, False, fast_pos, fast_caches)
                token = _sample(fast_logits, temperature, top_p, top_k, rng)
                codebooks.append(token)
            yield np.asarray(codebooks, dtype=np.int64)
            if step + 1 >= max_new_tokens:
                return
            column = np.concatenate([[semantic], np.asarray(codebooks)]).reshape(1, -1, 1)
            logits, hidden = self._slow_step(column, prompt_len + step, state)

    def decode_codes(self, codes: np.ndarray) -> np.ndarray:
        values = np.asarray(codes, dtype=np.int64)
        if values.ndim == 2:
            values = values[np.newaxis]
        audio = self.decoder.run(None, {"codes": values})[0]
        return np.asarray(audio, dtype=np.float32).reshape(-1)

    def synthesize(self, text: str, voice: str, **kwargs) -> tuple[np.ndarray, np.ndarray]:
        """Thread-safe full synthesis; returns (audio float32, codes [10, T])."""
        with self._synth_lock:
            frames = list(self.iter_codes(text=text, voice=voice, **kwargs))
            if not frames:
                raise RuntimeError("model produced no codec frames")
            codes = np.stack(frames, axis=1)
            return self.decode_codes(codes), codes

    # ── voice registration (from arktts_runtime.registration) ──────────

    def _ensure_default_voice(self):
        """Create the 'default' voice profile from the packaged reference."""
        voice_dir = self.voices.root / "default"
        if (voice_dir / "meta.json").is_file() and (voice_dir / "codes.npy").is_file():
            return
        reference = self.manifest.get("reference_codes")
        reference_text = self.manifest.get("reference_text", "")
        if not reference or not reference_text:
            raise RuntimeError("model package has no bundled reference voice")
        codes = np.load(self.model_dir / reference)
        voice_dir.mkdir(parents=True, exist_ok=True)
        np.save(voice_dir / "codes.npy", codes.astype(np.uint16))
        (voice_dir / "meta.json").write_text(
            json.dumps(
                {
                    "name": "default",
                    "reference_text": reference_text,
                    "shape": list(codes.shape),
                    "dtype": "uint16",
                    "sample_rate": self.sample_rate,
                    "source_kind": "packaged_reference",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _get_encoder(self) -> ort.InferenceSession:
        if self._encoder is None:
            registration_dir = self.model_dir / "registration"
            if not (registration_dir / "codec_encoder_fp16.onnx").is_file():
                raise RuntimeError("voice registration encoder not found in the model package")
            self._encoder = _session(registration_dir / "codec_encoder_fp16.onnx", self.threads)
        return self._encoder

    def register_voice(self, audio_bytes: bytes, transcript: str, name: str, overwrite: bool = True) -> dict:
        reference_text = " ".join(transcript.strip().split())
        if not reference_text:
            raise ValueError("reference text must not be empty")
        name = name.strip()
        if not name or len(name) > 64 or name in {".", ".."} or Path(name).name != name:
            raise ValueError("voice name must be one path component with at most 64 characters")
        registration_manifest = json.loads(
            (self.model_dir / "registration" / "registration_manifest.json").read_text()
        )
        target_rate = int(registration_manifest["sample_rate"])

        audio, source_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        duration = audio.size / max(1, int(source_rate))
        if duration < 0.5 or duration > 30.0:
            raise ValueError("reference audio duration must be between 0.5 and 30 seconds")
        if int(source_rate) != target_rate:
            factor = gcd(int(source_rate), target_rate)
            audio = resample_poly(audio, target_rate // factor, int(source_rate) // factor).astype(np.float32)
        padding = (-audio.size) % 2048
        if padding:
            audio = np.pad(audio, (0, padding))

        with self._synth_lock:
            encoder = self._get_encoder()
            input_type = encoder.get_inputs()[0].type
            values = audio.astype(np.float16 if input_type == "tensor(float16)" else np.float32)
            codes = np.asarray(encoder.run(None, {"audio": values.reshape(1, 1, -1)})[0], dtype=np.int64)
            self._encoder = None  # free the encoder session right away

        if codes.ndim == 3:
            codes = codes[0]
        if codes.ndim != 2 or codes.shape[0] != self.num_codebooks or codes.shape[1] == 0:
            raise RuntimeError(f"encoder returned invalid codes: {codes.shape}")

        self.voices.root.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=f".{name}.", dir=self.voices.root))
        try:
            np.save(temp / "codes.npy", codes.astype(np.uint16))
            meta = {
                "name": name,
                "reference_text": reference_text,
                "shape": list(codes.shape),
                "dtype": "uint16",
                "sample_rate": target_rate,
                "source_sha256": hashlib.sha256(audio_bytes).hexdigest(),
                "source_kind": "local_registration",
            }
            (temp / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            target = self.voices.root / name
            if target.exists():
                if not overwrite:
                    raise FileExistsError(f"voice already exists: {name}")
                shutil.rmtree(target)
            os.replace(temp, target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
        self.drop_prefix_cache(name)
        return meta
