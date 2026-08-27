# Plan: onnxruntime upgrade trial (1.19.2 → 1.22.1) for Audio8 TTS speed

Goal: find out whether a newer onnxruntime CPU build meaningfully speeds up the
Audio8 codec decoder (the CPU bottleneck: ~46 ms/frame FP16 on the dev machine,
~RTF 1.0 for decode alone), and only then ship the upgrade. Bench-first,
commit-last, fully reversible.

Success criteria:
- decode(57 frames) improves by >= 15% vs a same-session baseline, AND
- asrjs (sherpa-onnx + openwakeword) still imports/loads and transcribes, AND
- localtts test_speak still works end to end.
Abort condition: < 15% decoder gain, OR any consumer smoke test fails ->
revert to 1.19.2 and change nothing in the repo.

Why 1.22.1 and not 1.23.2: conservative step, Python 3.10.6 supported, and the
onnx-community Chatterbox ONNX export (a future TTS candidate) targets 1.22.1.
No new Python packages: ORT 1.22's dep set is identical to 1.19.2's and the
repo pins (flatbuffers 24.3.25, protobuf 5.28.2, sympy 1.14.0, numpy>=2.2.2)
all satisfy it.

Consumers at risk (must all be smoke tested):
- plugins/localtts/audio8_runtime.py (_session() at lines ~93-100): direct
  Python API, stable.
- plugins/asrjs/asrjs.py:607 `import sherpa_onnx` -> sherpa-onnx-core 1.13.2
  loads the onnxruntime DLL by ABI at runtime (pip enforces NOTHING here).
- plugins/asrjs/asrjs.py:32 + diag_coldstart.py: openwakeword 0.6.0 (declares
  onnxruntime as a dep, plain Python API).
- dist/igoor/_internal/: onnxruntime + sherpa_onnx bundled via hiddenimports
  (igoor.spec.txt:59-63) -> exe rebuild required, but no spec change.

All commands from the repo root (C:\AIKU\experiments\igoor, Git Bash, venv at
./venv, Python 3.10.6).

## Phase 0 - Fresh baseline on CURRENT onnxruntime 1.19.2

Machine load skews these numbers heavily; run phases 0 and 1 back to back under
similar conditions, and record both.

    ./venv/Scripts/python.exe -c "import onnxruntime; print(onnxruntime.__version__)"
    ./venv/Scripts/python.exe spikes/audio8/profile_stream.py | tee /tmp/ort_base.txt

Record: per-case "OLD total"/"NEW 1st"/"NEW total" AND, from the decoder sweep
below, decode(12/57/108):

    ./venv/Scripts/python.exe - <<'EOF'
    import time, numpy as np, onnxruntime as ort
    from pathlib import Path
    model = Path("spikes/audio8/model")
    codes = np.load("spikes/audio8/voices/default/codes.npy").astype(np.int64)
    o = ort.SessionOptions(); o.intra_op_num_threads = 5
    o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    o.log_severity_level = 3
    s = ort.InferenceSession(str(model/"codec_decoder_fp16.onnx"), sess_options=o, providers=["CPUExecutionProvider"])
    for n in (12, 57, 108):
        c = codes[:, :n][np.newaxis]; s.run(None, {"codes": c})
        t0 = time.perf_counter()
        for _ in range(3): s.run(None, {"codes": c})
        dt = (time.perf_counter()-t0)/3
        print(f"decode({n}) = {dt:.2f}s ({dt/n*1000:.0f} ms/frame)")
    EOF

Also note the user's manually-measured TTFA/RTF from the live app, if provided.

## Phase 1 - Trial install + re-bench (NO repo changes yet)

    ./venv/Scripts/pip.exe install onnxruntime==1.22.1
    ./venv/Scripts/python.exe spikes/audio8/profile_stream.py | tee /tmp/ort_122.txt
    (repeat the decoder sweep from Phase 0)

Decision: compare decode(57) and profile totals. < 15% better -> run Rollback
below, report "not worth it", stop. >= 15% -> continue.

## Phase 2 - Consumer smoke tests (still no repo changes)

1. ABI/import check (catches the sherpa-onnx-core DLL link):

       ./venv/Scripts/python.exe -c "import onnxruntime, sherpa_onnx, openwakeword; print('imports OK', onnxruntime.__version__)"

2. App-level smoke (asrjs + localtts together):
   - Temporarily disable other TTS plugins first if testing the speak path
     (backup %APPDATA%/igoor/settings.json, set plugins_activation.elevenlabstts
     and .ttsdefault to false; RESTORE afterwards).
   - Launch headless:  IGOOR_CLI=True ./venv/Scripts/python.exe main.py
   - Wait for ready:  curl http://127.0.0.1:9714/api/plugins/localtts/status
   - localtts:        curl -X POST http://127.0.0.1:9714/api/plugins/localtts/test_speak \
                        -H "Content-Type: application/json" -d '{"message":"Bonjour ! Ceci est un test."}'
   - asrjs readiness: check /api/plugins/asrjs settings/status + app logs for
     "sherpa-onnx model loaded" and openwakeword init; run one transcription if
     a mic/sample is available (asrjs has samples/ in its plugin folder).
   - Optional full streaming check: ./venv/Scripts/python.exe
     spikes/audio8/e2e_stream_client.py (needs the /ws/asrjs trick it already
     implements).
   - Stop the app, restore settings.json.

## Phase 3 - Commit the change (only after Phase 1 + 2 pass)

Exactly one line:
- requirements.txt:108  onnxruntime==1.19.2  ->  onnxruntime==1.22.1

No changes to: igoor.spec.txt (same hiddenimports), asrjs, localtts code,
locales, settings. No new dependencies.
Then:  ./venv/Scripts/python.exe -m py_compile plugins/localtts/audio8_runtime.py plugins/localtts/localtts.py

## Phase 4 - Exe rebuild + packaged verification

    create_exe_fast.bat
    - confirm dist/igoor/_internal/onnxruntime/ exists and
      dist-info folder is onnxruntime-1.22.1.dist-info
    - launch the exe, repeat the localtts test_speak and asrjs readiness checks

## Rollback (at any point before Phase 3)

    ./venv/Scripts/pip.exe install onnxruntime==1.19.2
    git checkout -- requirements.txt   (only if Phase 3 was done)

## Notes / known traps

- Benchmarks are load-sensitive: never compare numbers taken hours apart or
  during heavy background work; always re-baseline in the same session.
- sherpa-onnx-core has NO pip-level constraint on onnxruntime; the DLL link is
  only proven by actually importing and running it (Phase 2 step 1 + app boot).
- If ORT 1.22 implements ConvInteger for the decoder's convs (1.19.2 does not),
  do NOT chase INT8 dynamic quantization anyway: static INT8 was measured 6x
  SLOWER with broken output on 1.19.2 (see spikes/audio8/quantize_decoder_test.py).
- If decode gets materially faster, re-run spikes/audio8/profile_stream.py and
  report the new TTFA/gap numbers to the user; sentence-level streaming gap
  behavior improves proportionally.
