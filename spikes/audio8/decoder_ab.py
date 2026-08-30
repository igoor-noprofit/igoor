"""Controlled A/B decoder benchmark: min-of-N wall times (robust to
background load spikes) for the Audio8 codec decoder.
"""
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

model = Path(__file__).resolve().parent / "model"
codes = np.load(model.parent / "voices" / "default" / "codes.npy").astype(np.int64)

o = ort.SessionOptions()
o.intra_op_num_threads = 5
o.inter_op_num_threads = 2
o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
o.log_severity_level = 3

print(f"onnxruntime {ort.__version__}")
for n in (12, 57, 108):
    c = codes[:, :n][np.newaxis]
    best = float("inf")
    for session_try in range(3):  # fresh session each round, keep the min
        s = ort.InferenceSession(
            str(model / "codec_decoder_fp16.onnx"),
            sess_options=o, providers=["CPUExecutionProvider"],
        )
        s.run(None, {"codes": c})
        t0 = time.perf_counter()
        for _ in range(5):
            s.run(None, {"codes": c})
        best = min(best, (time.perf_counter() - t0) / 5)
    print(f"decode({n:>3}) min = {best:.2f}s ({best / n * 1000:.0f} ms/frame)")
