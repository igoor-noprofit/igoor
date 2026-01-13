## Fix Multiple Dependency Conflicts with pyannote Packages

**Problem**: pyannote packages require newer versions of several dependencies:
- `pyannote-audio 4.0.3` requires: `huggingface-hub>=0.28.1`, `safetensors>=0.5.2`, `soundfile>=0.13.1`
- `pyannote-core 6.0.1` requires: `numpy>=2.0`
- `pyannote-metrics 4.0.0` requires: `numpy>=2.2.2`, `scikit-learn>=1.6.1`, `scipy>=1.15.1`
- `pyannote-pipeline 4.0.0` requires: `filelock>=3.17.0`, `tqdm>=4.67.1`

**Solution**: Update these packages in requirements.txt to satisfy all requirements:
- `filelock==3.16.1` → `filelock>=3.17.0`
- `huggingface-hub==0.26.1` → `huggingface-hub>=0.28.1`
- `numpy==1.26.4` → `numpy>=2.2.2`
- `safetensors==0.4.5` → `safetensors>=0.5.2`
- `scipy==1.12.0` → `scipy>=1.15.1`
- `scikit-learn==1.5.2` → `scikit-learn>=1.6.1`
- `soundfile==0.12.1` → `soundfile>=0.13.1`
- `tqdm==4.66.5` → `tqdm>=4.67.1`

This will resolve all the conflicts with pyannote packages.