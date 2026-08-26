"""Audio8 TTS feasibility spike: Windows 10 + Python 3.10 + IGOOR venv deps.

Creates the default voice from the packaged reference, synthesizes in
English and French, writes WAVs and reports wall-clock speed.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "Audio8_TTS" / "onnx_runtime"))
sys.path.insert(0, str(HERE))

from runtime01 import Runtime01  # noqa: E402

MODEL_DIR = HERE / "model"
VOICES_DIR = HERE / "voices"
OUT_DIR = HERE / "outputs"


def ensure_default_voice() -> None:
    manifest = json.loads((MODEL_DIR / "runtime_manifest.json").read_text())
    voice_dir = VOICES_DIR / "default"
    meta_path = voice_dir / "meta.json"
    codes_path = voice_dir / "codes.npy"
    if meta_path.is_file() and codes_path.is_file():
        return
    voice_dir.mkdir(parents=True, exist_ok=True)
    codes = np.load(MODEL_DIR / manifest["reference_codes"])
    print("reference codes:", codes.shape, codes.dtype)
    np.save(codes_path, codes.astype(np.uint16))
    meta_path.write_text(
        json.dumps(
            {
                "name": "default",
                "reference_text": manifest["reference_text"],
                "shape": list(codes.shape),
                "dtype": "uint16",
                "sample_rate": manifest["sample_rate"],
                "source_kind": "packaged_reference",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("created default voice profile")


def main() -> None:
    ensure_default_voice()
    t0 = time.time()
    rt = Runtime01(MODEL_DIR, VOICES_DIR, threads=5)
    print("sessions loaded in %.1fs" % (time.time() - t0))

    texts = {
        "en": "Hello! This is a local text to speech test running fully offline on Windows.",
        "fr": "Bonjour ! Ceci est un test de synthèse vocale locale, exécuté hors ligne.",
    }
    OUT_DIR.mkdir(exist_ok=True)
    for lang, text in texts.items():
        t0 = time.time()
        audio, codes = rt.synthesize(
            text=text,
            voice="default",
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            seed=42,
        )
        elapsed = time.time() - t0
        duration = audio.size / rt.manifest["sample_rate"]
        out = OUT_DIR / f"spike_{lang}.wav"
        sf.write(str(out), audio, int(rt.manifest["sample_rate"]))
        print(
            f"[{lang}] {elapsed:.1f}s to synthesize {duration:.1f}s audio "
            f"(RTF {elapsed / duration:.2f}x realtime) -> {out} peaks="
            f"{np.abs(audio).max():.3f}"
        )


if __name__ == "__main__":
    main()
