"""Minimal inference adapter for Audio8-TTS-Preview-0.1B-ONNX-INT8 on
Python 3.10 / onnxruntime 1.19.

The published arktts_runtime targets the 0.6B-INT4 graphs; the 0.1B slow AR
uses a different interface: per-token `codes` [1,11,1], scalar `position`,
stacked attention caches plus Mamba conv/ssm states, and relative semantic
logits (4096 semantic + 1 EOS). The fast AR and codec decoder interfaces are
identical to the published runtime, so those parts are reused.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import onnxruntime as ort

from arktts_runtime.prompt import PromptBuilder
from arktts_runtime.runtime import _sample, _session
from arktts_runtime.voices import VoiceStore


class Runtime01:
    def __init__(self, model_dir: Path, voices_dir: Path, threads: int | None = 5):
        self.model_dir = Path(model_dir).resolve()
        self.manifest = json.loads((self.model_dir / "runtime_manifest.json").read_text())
        self.slow = _session(self.model_dir / "slow_ar_int8.onnx", threads)
        self.fast = _session(self.model_dir / "fast_ar_int8.onnx", threads)
        self.decoder = _session(self.model_dir / "codec_decoder_fp16.onnx", threads)
        self.prompt_builder = PromptBuilder(
            self.model_dir / "tokenizer",
            self.manifest["semantic_begin_id"],
            self.manifest["num_codebooks"],
        )
        self.voices = VoiceStore(Path(voices_dir), self.manifest["num_codebooks"])
        self._slow_input_meta = {i.name: i for i in self.slow.get_inputs()}
        self._fast_inputs = {i.name: i for i in self.fast.get_inputs()}
        self._num_layers = int(self.manifest["num_layers"])
        self._num_fast_layers = int(self.manifest["num_fast_layers"])

    # --- slow AR (per-token recurrent graph with stacked state) ---

    def _zero_slow_state(self):
        def zeros(name):
            meta = self._slow_input_meta[name]
            return np.zeros(meta.shape, dtype=np.float32)

        return {
            "cache_keys": zeros("cache_keys"),
            "cache_values": zeros("cache_values"),
            "conv_states": zeros("conv_states"),
            "ssm_states": zeros("ssm_states"),
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

    # --- fast AR (identical to published runtime) ---

    def _zero_fast_caches(self):
        shape = (1, int(self.manifest["fast_n_local_heads"]), int(self.manifest["num_codebooks"]), int(self.manifest["fast_head_dim"]))
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

    # --- sampling: relative layout, logits[4097] = 4096 semantic + EOS ---

    def _sample_semantic(self, logits, previous, temperature, top_p, top_k, rng):
        values = np.asarray(logits).reshape(-1)
        eos = values.size - 1
        begin = int(self.manifest["semantic_begin_id"])
        idx = _sample(values, temperature, top_p, top_k, rng)
        if idx == eos:
            return None
        semantic = begin + int(idx)
        if semantic in previous:
            high = _sample(values, 1.0, 0.9, top_k, rng)
            if high != eos:
                semantic = begin + int(high)
        return semantic

    # --- main loop ---

    def iter_codes(
        self,
        text: str,
        voice: str,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        seed: int = 42,
        stop_event: threading.Event | None = None,
    ) -> Iterator[np.ndarray]:
        reference_codes, meta = self.voices.load(voice)
        prompt = self.prompt_builder.build(text, meta["reference_text"], reference_codes)
        prompt_len = int(prompt.shape[2])
        max_seq_len = int(self.manifest["max_seq_len"])
        if prompt_len >= max_seq_len:
            raise ValueError(f"prompt length {prompt_len} exceeds max sequence length {max_seq_len}")
        max_new_tokens = min(int(max_new_tokens), max_seq_len - prompt_len)
        rng = np.random.default_rng(int(seed))

        state = self._zero_slow_state()
        for t in range(prompt_len):
            logits, hidden = self._slow_step(prompt[:, :, t : t + 1], t, state)

        previous: list[int] = []
        begin = int(self.manifest["semantic_begin_id"])
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
            token = min(max(semantic - begin, 0), codebook_size - 1)
            codebooks = [token]
            for fast_pos in range(1, int(self.manifest["num_codebooks"])):
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

    def synthesize(self, **kwargs) -> tuple[np.ndarray, np.ndarray]:
        frames = list(self.iter_codes(**kwargs))
        if not frames:
            raise RuntimeError("model produced no codec frames")
        codes = np.stack(frames, axis=1)
        return self.decode_codes(codes), codes
