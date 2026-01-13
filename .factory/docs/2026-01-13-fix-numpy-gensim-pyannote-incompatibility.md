## Fix numpy/gensim/pyannote Incompatibility

**Problem**: Fundamental version conflict:
- `gensim 4.3.3` requires `numpy<2.0 and >=1.18.5`
- `pyannote-core 6.0.1` requires `numpy>=2.0`
- `pyannote-metrics 4.0.0` requires `numpy>=2.2.2`

**Solution Options**:

**Option A**: Upgrade gensim to version that supports numpy 2.x (if available)
- Try `gensim>=4.4.0` or check latest version
- This would allow using numpy>=2.2.2

**Option B**: Revert numpy to 1.26.4 and downgrade pyannote packages
- Revert `numpy>=2.2.2` back to `numpy==1.26.4`
- Find pyannote versions that work with numpy 1.x
- This maintains gensim compatibility

**Recommendation**: Try Option A first (upgrade gensim), fall back to Option B if needed.

**Changes to attempt**:
- File: `C:\AIKU\experiments\igoor\requirements.txt`
- Change: `gensim==4.3.3` → `gensim>=4.4.0` (or latest compatible version)
- Keep: `numpy>=2.2.2`