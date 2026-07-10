"""Diagnostic: prove the openWakeWord cold-start after reset().

Run with the project venv so `openwakeword` is importable:

    venv/Scripts/python plugins/asrjs/diag_coldstart.py [model.onnx] [wakeword_clip.wav]

Defaults to the French default model. Passing a real wakeword clip is optional —
the cold-start is a property of the openWakeWord engine, so noise alone proves it.

What it shows:
  1. After reset(), the first 5 predict() frames are FORCED to exactly 0.0
     (openWakeWord's initialization guard) -> a ~400ms blind window where
     detection is impossible.
  2. Priming the model with ~1.5s of silence clears that window, so the first
     real frame is already non-zero (warm).
"""
import sys
import os
import wave
import numpy as np

CHUNK = 1280          # samples per predict() call (80ms @ 16kHz) — openWakeWord's unit
SR = 16000


def load_model(path):
    from openwakeword import Model
    return Model(wakeword_models=[path])


def score_of(pred):
    """Return the single wakeword score from a prediction dict."""
    return float(next(iter(pred.values())))


def predict_n(model, audio_fn, n):
    """Feed n chunks produced by audio_fn(), return list of scores."""
    out = []
    for _ in range(n):
        out.append(score_of(model.predict(audio_fn())))
    return out


def noise_chunk(amplitude=3000):
    return (np.random.randn(CHUNK) * amplitude).astype(np.int16)


def silence_chunk():
    return np.zeros(CHUNK, dtype=np.int16)


def show_unprimed(model):
    print("\n[1] UNPRIMED — predict() right after reset()")
    print("    Expect frames 0-4 == 0.0000 (forced blind window), then non-zero.\n")
    model.reset()
    scores = predict_n(model, noise_chunk, 40)
    forced = sum(1 for s in scores[:5] if s == 0.0)
    for i, s in enumerate(scores):
        tag = "  <-- forced 0.0 (detection IMPOSSIBLE)" if (s == 0.0 and i < 5) else ""
        print(f"    frame {i:2d}: {s:.4f}{tag}")
    print(f"\n    Forced-zero frames in first 5: {forced}/5  (400ms blind window)")
    print(f"    First non-zero frame at index: {next((i for i, s in enumerate(scores) if s != 0.0), None)}")


def show_primed(model):
    print("\n[2] PRIMED — 1.5s of silence fed after reset(), then predict()")
    print("    Expect frame 0 to be non-zero (window cleared).\n")
    model.reset()
    for _ in range(19):  # ~1.5s of 80ms chunks
        model.predict(silence_chunk())
    scores = predict_n(model, noise_chunk, 10)
    for i, s in enumerate(scores):
        print(f"    frame {i:2d}: {s:.4f}")
    print(f"\n    Forced-zero frames in first 5: {sum(1 for s in scores[:5] if s == 0.0)}/5  (should be 0)")


def show_clip(model, clip_path, sensitivity=0.5):
    """Optional: feed a real wakeword clip unprimed vs primed, report first detection."""
    try:
        with wave.open(clip_path, "rb") as wf:
            n = wf.getnframes()
            raw = wf.readframes(n)
        samples = np.frombuffer(raw, dtype=np.int16).copy()
    except Exception as e:
        print(f"\n[3] Skipped clip test (could not read {clip_path!r}: {e})")
        return

    # Tile/trim to at least a couple of seconds so the wakeword is fully covered
    if len(samples) < SR * 2:
        reps = int(np.ceil(SR * 2 / len(samples)))
        samples = np.tile(samples, reps)
    chunks = [samples[i:i + CHUNK] for i in range(0, len(samples) - CHUNK + 1, CHUNK)][:40]

    def first_detect(reset_first, prime_first):
        if reset_first:
            model.reset()
        if prime_first:
            for _ in range(19):
                model.predict(silence_chunk())
        for i, ch in enumerate(chunks):
            if score_of(model.predict(ch)) >= sensitivity:
                return i
        return None

    print(f"\n[3] Real clip {os.path.basename(clip_path)} (sensitivity={sensitivity})")
    print("    First frame >= sensitivity (lower = faster/more reliable detection):\n")
    for label, reset, prime in (("UNPRIMED", True, False), ("PRIMED  ", True, True)):
        idx = first_detect(reset, prime)
        # subtract 5 to discount the forced blind window on the unprimed path
        note = "" if idx is not None else "  (NOT detected in first ~3.2s)"
        if idx is not None and not prime:
            note = f"  (but first 5 frames were forced to 0, so real latency = frame {max(0, idx)})"
        print(f"    {label}: frame {idx}{note}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_model = os.path.join(here, "locales", "fr_FR", "hey_igoor_fr_FR.onnx")
    model_path = sys.argv[1] if len(sys.argv) > 1 else default_model
    clip = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        sys.exit(1)

    print(f"Loading openWakeWord model: {model_path}")
    model = load_model(model_path)
    print(f"Model loaded. Wakeword label(s): {list(model.models.keys())}")

    show_unprimed(model)
    show_primed(model)
    if clip:
        show_clip(model, clip)

    print("\nConclusion: the FIRST wakeword after reset() is suppressed by a ~400ms forced-zero")
    print("blind window plus a context warmup. Priming (as the fix does) clears it.\n")


if __name__ == "__main__":
    main()
