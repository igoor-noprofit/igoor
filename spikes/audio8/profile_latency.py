"""Latency profile: prefill vs decode, time-to-first-audio for short
conversational sentences (IGOOR use case) on the local machine.

Time-to-first-audio models the streaming approach: generate 12 codec frames
(~0.56s of audio at 21.5 frames/s), decode that window, start playback.
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Audio8_TTS" / "onnx_runtime"))
sys.path.insert(0, str(HERE))

from runtime01 import Runtime01  # noqa: E402

FRAMES_PER_CHUNK = 12  # same chunking as the published stream() helper


def profile(rt, text, seed=7):
    t0 = time.perf_counter()
    stamps = []
    frames = []
    for frame in rt.iter_codes(text=text, voice="default", max_new_tokens=400, seed=seed):
        stamps.append(time.perf_counter() - t0)
        frames.append(frame)
    if len(frames) < FRAMES_PER_CHUNK + 5:
        raise RuntimeError(f"too few frames: {len(frames)}")
    steady = (stamps[-1] - stamps[10]) / (len(stamps) - 11)
    prefill = stamps[0] - steady  # first frame = prefill + one generated frame

    window = np.stack(frames[:FRAMES_PER_CHUNK], axis=1)
    td = time.perf_counter()
    audio = rt.decode_codes(window)
    decode_chunk = time.perf_counter() - td

    duration = len(frames) / 21.5
    total = stamps[-1] + decode_chunk
    return {
        "frames": len(frames),
        "audio_s": duration,
        "prefill_s": prefill,
        "ms_per_frame": steady * 1000,
        "decode_chunk_s": decode_chunk,
        "first_audio_s": stamps[FRAMES_PER_CHUNK - 1] + decode_chunk,
        "total_s": total,
        "rtf": total / duration,
        "audio": audio,
    }


SENTENCES = [
    ("fr-short", "Bonjour, comment allez-vous aujourd'hui ?"),
    ("fr-reply", "Je suis là, que puis-je faire pour vous ?"),
    ("en-short", "Sure, I can help with that."),
    ("en-reply", "What would you like to drink?"),
    ("fr-long", "Bonjour ! Ceci est un test de synthèse vocale locale, exécuté hors ligne sur Windows."),
]


def main() -> None:
    rt = Runtime01(HERE / "model", HERE / "voices", threads=5)
    print(f"{'sentence':<10} {'frames':>6} {'audio':>6} {'prefill':>8} {'ms/frame':>9} "
          f"{'1st-audio':>9} {'total':>7} {'RTF':>5}")
    for name, text in SENTENCES:
        r = profile(rt, text)
        print(f"{name:<10} {r['frames']:>6} {r['audio_s']:>5.1f}s {r['prefill_s']:>7.2f}s "
              f"{r['ms_per_frame']:>8.0f} {r['first_audio_s']:>8.2f}s {r['total_s']:>6.1f}s "
              f"{r['rtf']:>5.2f}")

    print("\nthreads sweep (fr-short):")
    for threads in (3, 4, 5, 6):
        rt_t = Runtime01(HERE / "model", HERE / "voices", threads=threads)
        r = profile(rt_t, SENTENCES[0][1])
        print(f"  threads={threads}: prefill {r['prefill_s']:.2f}s, {r['ms_per_frame']:.0f} ms/frame, "
              f"first audio {r['first_audio_s']:.2f}s, RTF {r['rtf']:.2f}")


if __name__ == "__main__":
    main()
