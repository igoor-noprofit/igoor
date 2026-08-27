"""Sentence-pipelined latency profile for the plugin's Audio8Runtime.

Compares the old whole-clip path (synthesize() on the full text, one WAV
after all generation) against the streaming speak_func path (per-sentence
synthesize, chunks sent as they are produced). Whole-sentence decode is the
model's validated batch mode: the codec decoder produces cold-start
transients on partial windows, and the upstream sliding-context streaming
decode costs >10x realtime on CPU.
"""
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # repo root, for plugins.localtts

from plugins.localtts.audio8_runtime import Audio8Runtime  # noqa: E402

FRAMES_PER_SECOND = 21.5  # model card: ~21.5 codec frames per second

SENTENCES = [
    ("fr-short", "Bonjour, comment allez-vous aujourd'hui ?"),
    ("fr-reply", "Je suis là, que puis-je faire pour vous ?"),
    ("en-short", "Sure, I can help with that."),
    ("it-short", "Ciao, come stai oggi?"),
    ("fr-long", "Bonjour ! Ceci est un test de synthèse vocale locale, exécuté hors ligne sur Windows."),
    ("fr-multi", "Bonjour ! Je vais bien, merci de demander. Aujourd'hui nous testons la synthèse vocale en flux. "
                 "Chaque phrase est envoyée dès qu'elle est prête. Le reste continue pendant la lecture."),
    ("en-multi", "Hello! I am doing great today. This reply is streamed sentence by sentence. "
                 "You should hear the first one while the rest is still generating."),
]


def split_sentences(text):
    parts = [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]
    return parts


def pcm_seconds(audio):
    return audio.size / 44100


def main() -> None:
    rt = Audio8Runtime(HERE / "model", HERE / "voices", threads=5)
    rt._ensure_default_voice()

    t0 = time.perf_counter()
    rt.get_prefix_state("default")
    print(f"prefix cache build: {time.perf_counter() - t0:.2f}s (one-time per voice, done at model load)\n")

    print(f"{'case':<10} {'#snt':>4} {'audio':>6} {'OLD total':>10} {'NEW 1st':>8} {'NEW total':>10} {'gap':>5}")
    for name, text in SENTENCES:
        # OLD path: whole-clip synthesis (time-to-first-audio == total time)
        t0 = time.perf_counter()
        full, _ = rt.synthesize(text=text, voice="default", seed=7)
        t_old = time.perf_counter() - t0

        # NEW path: per-sentence synthesis, chunk timestamps as they complete
        arrivals = []  # (t_available, duration_s)
        t0 = time.perf_counter()
        for sentence in split_sentences(text):
            audio, _ = rt.synthesize(text=sentence, voice="default", seed=7)
            arrivals.append((time.perf_counter() - t0, pcm_seconds(audio)))
        t_new = time.perf_counter() - t0

        # playback simulation: continuous from first chunk, starves if a
        # sentence is not ready when the previous ones have finished playing
        playhead = arrivals[0][0]
        gap = 0.0
        for t_avail, dur in arrivals:
            if t_avail > playhead:
                gap += t_avail - playhead
                playhead = t_avail
            playhead += dur

        dur_total = sum(d for _, d in arrivals)
        print(f"{name:<10} {len(arrivals):>4} {dur_total:>5.1f}s {t_old:>9.2f}s {arrivals[0][0]:>7.2f}s "
              f"{t_new:>9.2f}s {gap:>4.1f}s")

    print("\nOLD time-to-first-audio = OLD total (one WAV sent after full generation).")
    print("NEW time-to-first-audio = first sentence synthesized + decoded.")
    print("'gap' = simulated mid-playback starvation while waiting for later sentences.")


if __name__ == "__main__":
    main()
