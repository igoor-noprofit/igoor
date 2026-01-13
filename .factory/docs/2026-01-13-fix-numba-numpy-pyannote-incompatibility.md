## Fix numba/numpy/pyannote Incompatibility

**Problem**: `numba 0.60.0` requires `numpy<2.1`, but `pyannote-metrics 4.0.0` requires `numpy>=2.2.2`.

**Solution**: Upgrade numba to version 0.62.0, which supports numpy 2.3 and would be compatible with `numpy>=2.2.2`.

**Change**:
- File: `C:\AIKU\experiments\igoor\requirements.txt`
- Change: `numba==0.60.0` → `numba>=0.62.0`

This will resolve the conflict since numba 0.62.0 officially supports numpy 2.3, making it compatible with `numpy>=2.2.2`.