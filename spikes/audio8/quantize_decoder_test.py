"""INT8 quantization experiment for the Audio8 codec decoder (the CPU
bottleneck: ~46 ms/frame in FP16). Builds dynamic-INT8 and static-INT8
(calibrated on real voice codes) variants and benchmarks them against the
FP16 original, checking output fidelity against an FP32 conversion.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, numpy_helper

HERE = Path(__file__).resolve().parent
MODEL = HERE / "model"
MANIFEST = json.loads((MODEL / "runtime_manifest.json").read_text())

FP16 = MODEL / MANIFEST["codec_models"]["fp16"]
FP32_TMP = MODEL / "codec_decoder_fp32_tmp.onnx"
INT8_DYN = MODEL / "codec_decoder_int8_dyn_tmp.onnx"
INT8_STA = MODEL / "codec_decoder_int8_static_tmp.onnx"


def to_fp32(src: Path, dst: Path) -> None:
    m = onnx.load(str(src))
    m = onnx.shape_inference.infer_shapes(m)
    for i, init in enumerate(m.graph.initializer):
        if init.data_type == TensorProto.FLOAT16:
            m.graph.initializer[i].CopyFrom(
                numpy_helper.from_array(numpy_helper.to_array(init).astype(np.float32), init.name)
            )
    def flip(v):
        if v.type.tensor_type.elem_type == TensorProto.FLOAT16:
            v.type.tensor_type.elem_type = TensorProto.FLOAT
    for v in list(m.graph.input) + list(m.graph.value_info) + list(m.graph.output):
        flip(v)
    for n in m.graph.node:
        if n.op_type == "Cast":
            for a in n.attribute:
                if a.i == TensorProto.FLOAT16:
                    a.i = TensorProto.FLOAT
        if n.op_type == "Constant":
            for a in n.attribute:
                if a.name == "value" and a.t.data_type == TensorProto.FLOAT16:
                    a.t.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(a.t).astype(np.float32), a.t.name))
    onnx.checker.check_model(m)
    onnx.save(m, str(dst))


def session(path: Path, threads: int = 5) -> ort.InferenceSession:
    o = ort.SessionOptions()
    o.intra_op_num_threads = threads
    o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    o.log_severity_level = 3
    return ort.InferenceSession(str(path), sess_options=o, providers=["CPUExecutionProvider"])


def bench(sess, codes, repeats=3) -> float:
    sess.run(None, {"codes": codes})
    t0 = time.perf_counter()
    for _ in range(repeats):
        sess.run(None, {"codes": codes})
    return (time.perf_counter() - t0) / repeats


def main() -> None:
    codes_all = np.load(HERE / "voices" / "default" / "codes.npy").astype(np.int64)
    probes = {
        12: codes_all[:, :12][np.newaxis],
        57: codes_all[:, :57][np.newaxis],
        108: codes_all[:, :108][np.newaxis],
    }

    to_fp32(FP16, FP32_TMP)

    # static INT8 calibrated on real code windows
    from onnxruntime.quantization import (
        CalibrationDataReader, quantize_static, QuantFormat, CalibrationMethod, QuantType,
    )

    lengths = [12, 24, 57, 108, 200]

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.reps = [
                {"codes": np.ascontiguousarray(codes_all[:, :n][np.newaxis])}
                for n in lengths if n <= codes_all.shape[1]
            ]
            self.i = 0

        def get_next(self):
            if self.i >= len(self.reps):
                return None
            rep = self.reps[self.i]
            self.i += 1
            return rep

    quantize_static(
        FP32_TMP, INT8_STA, Reader(),
        quant_format=QuantFormat.QOperator,
        activation_type=QuantType.QInt8, weight_type=QuantType.QInt8,
        calibrate_method=CalibrationMethod.MinMax,
    )

    variants = {
        "fp16 (production)": session(FP16),
        "fp32": session(FP32_TMP),
        "int8 static": session(INT8_STA),
    }

    ref57 = None
    for name, sess in variants.items():
        row = []
        for n, codes in probes.items():
            row.append(f"decode({n})={bench(sess, codes):.2f}s")
        out57 = np.asarray(sess.run(None, {"codes": probes[57]})[0], dtype=np.float32).reshape(-1)
        if ref57 is None:
            ref57 = out57
            diff = "reference"
        else:
            d = np.abs(out57 - ref57)
            diff = f"max diff {d.max():.4f} ({d.max()*32767:.0f} LSB), mean {d.mean():.5f}"
        print(f"{name:<18} {'  '.join(row)}   vs fp16: {diff}")


if __name__ == "__main__":
    main()
