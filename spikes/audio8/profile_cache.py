"""Prefix-state caching test: the prompt prefix (system template + reference
voice codes) is identical for every utterance with a given voice, so the
slow-AR state after prefilling it can be computed once and reused. Measures
time-to-first-audio with a warm cache and verifies identical output vs a
cold full prefill.
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Audio8_TTS" / "onnx_runtime"))
sys.path.insert(0, str(HERE))

from arktts_runtime.prompt import clean_text, format_reference_text  # noqa: E402
from runtime01 import Runtime01  # noqa: E402

FRAMES_PER_CHUNK = 12


def build_prompt(pb, text, reference_text, reference_codes):
    """Mirror of PromptBuilder.build that also returns the fixed-prefix
    boundary (everything before <|im_end|>: template + reference speech)."""
    codes = np.asarray(reference_codes, dtype=np.int64)
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
    prefix = [t for part in prefix_parts for t in pb.encode_text(part)]
    suffix = [t for part in suffix_parts for t in pb.encode_text(part)]
    semantic_ids = (codes[0] + pb.semantic_begin_id).tolist()
    row0 = np.asarray(prefix + semantic_ids + suffix, dtype=np.int64)
    values = np.zeros((pb.num_codebooks + 1, row0.size), dtype=np.int64)
    values[0] = row0
    begin = len(prefix)
    values[1:, begin : begin + codes.shape[1]] = codes
    return values[np.newaxis], begin + codes.shape[1]


def prefill(rt, prompt, start, end, state=None):
    """Feed prompt positions start..end-1; return state and last logits/hidden."""
    if state is None:
        state = rt._zero_slow_state()
    for t in range(start, end):
        logits, hidden = rt._slow_step(prompt[:, :, t : t + 1], t, state)
    return state, logits, hidden


def clone_state(state):
    return {k: v.copy() for k, v in state.items()}


def generate(rt, prompt_len, logits, hidden, state, seed, max_new_tokens=400):
    rng = np.random.default_rng(seed)
    frames = []
    stamps = []
    previous = []
    begin = int(rt.manifest["semantic_begin_id"])
    codebook_size = int(rt.manifest["codebook_size"])
    t0 = time.perf_counter()
    for step in range(max_new_tokens):
        semantic = rt._sample_semantic(logits, previous, 0.7, 0.9, 50, rng)
        if semantic is None:
            break
        previous = (previous + [semantic])[-10:]
        fast_caches = rt._zero_fast_caches()
        rt._fast_step(hidden, 0, True, 0, fast_caches)
        token = min(max(semantic - begin, 0), codebook_size - 1)
        codebooks = [token]
        for fp in range(1, int(rt.manifest["num_codebooks"])):
            fl = rt._fast_step(hidden, token, False, fp, fast_caches)
            token = int(np.argmax(fl))
            codebooks.append(token)
        frames.append(np.asarray(codebooks, dtype=np.int64))
        stamps.append(time.perf_counter() - t0)
        if step + 1 >= max_new_tokens:
            break
        column = np.concatenate([[semantic], np.asarray(codebooks)]).reshape(1, -1, 1)
        logits, hidden = rt._slow_step(column, prompt_len + step, state)
    return frames, stamps


def run_cached(rt, cached, text, meta, reference_codes, seed=7):
    prompt, boundary = build_prompt(rt.prompt_builder, text, meta["reference_text"], reference_codes)
    state, logits, hidden = prefill(rt, prompt, boundary, prompt.shape[2], clone_state(cached))
    return prompt.shape[2], (state, logits, hidden)


def run_cold(rt, text, meta, reference_codes, seed=7):
    prompt, _ = build_prompt(rt.prompt_builder, text, meta["reference_text"], reference_codes)
    state, logits, hidden = prefill(rt, prompt, 0, prompt.shape[2])
    return prompt.shape[2], (state, logits, hidden)


def main() -> None:
    rt = Runtime01(HERE / "model", HERE / "voices", threads=5)
    reference_codes, meta = rt.voices.load("default")

    # 1) one-time prefix cache build (fixed cost per voice)
    probe, boundary = build_prompt(rt.prompt_builder, "x", meta["reference_text"], reference_codes)
    t0 = time.perf_counter()
    cached, _, _ = prefill(rt, probe, 0, boundary)
    print(f"prefix cache build: {time.perf_counter() - t0:.2f}s for {boundary} tokens (one-time per voice)")

    # 2) correctness: identical frames cold vs warm
    text = "Bonjour, comment allez-vous aujourd'hui ?"
    plen, cold_ctx = run_cold(rt, text, meta, reference_codes)
    cold_frames, _ = generate(rt, plen, cold_ctx[1], cold_ctx[2], cold_ctx[0], seed=7)
    plen, warm_ctx = run_cached(rt, cached, text, meta, reference_codes)
    warm_frames, _ = generate(rt, plen, warm_ctx[1], warm_ctx[2], warm_ctx[0], seed=7)
    same = len(cold_frames) == len(warm_frames) and all(
        (a == b).all() for a, b in zip(cold_frames, warm_frames)
    )
    print(f"cold vs warm identical output: {same} ({len(cold_frames)} vs {len(warm_frames)} frames)")

    # 3) warm-cache latency per sentence
    print(f"\n{'sentence':<10} {'suffix_pf':>9} {'1st-audio':>9} {'ms/frame':>9} {'total':>7}")
    for name, text in [
        ("fr-short", "Bonjour, comment allez-vous aujourd'hui ?"),
        ("fr-reply", "Je suis là, que puis-je faire pour vous ?"),
        ("en-short", "Sure, I can help with that."),
        ("fr-long", "Bonjour ! Ceci est un test de synthèse vocale locale, exécuté hors ligne sur Windows."),
    ]:
        t0 = time.perf_counter()
        plen, ctx = run_cached(rt, cached, text, meta, reference_codes)
        t_suffix = time.perf_counter() - t0
        frames, stamps = generate(rt, plen, ctx[1], ctx[2], ctx[0], seed=7)
        window = np.stack(frames[:FRAMES_PER_CHUNK], axis=1)
        td = time.perf_counter()
        rt.decode_codes(window)
        t_decode = time.perf_counter() - td
        first_audio = t_suffix + stamps[FRAMES_PER_CHUNK - 1] + t_decode
        steady = (stamps[-1] - stamps[10]) / (len(stamps) - 11) if len(stamps) > 15 else stamps[-1] / len(stamps)
        total = t_suffix + stamps[-1] + t_decode
        dur = len(frames) / 21.5
        print(f"{name:<10} {t_suffix:>8.2f}s {first_audio:>8.2f}s {steady * 1000:>8.0f} "
              f"{total:>6.1f}s  (audio {dur:.1f}s, RTF {total / dur:.2f})")


if __name__ == "__main__":
    main()
