## Fix speechbrain.utils.fetching Import Error

**Problem**: The `speechbrain.utils.fetching` module doesn't exist in speechbrain 0.5.15. The code tries to import it and patch `link_with_strategy` to use COPY on Windows, but this module has been removed or moved.

**Solution**: Remove the fetching module imports and patching code from `plugins/speakerid/speechbrain.py` since the module doesn't exist in current speechbrain version.

**Changes**:
- File: `C:\AIKU\experiments\igoor\plugins\speakerid\speechbrain.py`
- Lines 23-32: Remove the importing and patching of `speechbrain.utils.fetching`
- The code block to remove:
```python
import speechbrain.utils.fetching as fetching
from speechbrain.utils.fetching import LocalStrategy

# Force COPY strategy
original_link = fetching.link_with_strategy

def patched_link(src, dst, strategy=None):
    # Always use COPY on Windows to avoid symlink issues
    return original_link(src, dst, LocalStrategy.COPY)

fetching.link_with_strategy = patched_link
```

This will allow the speakerid plugin to load successfully. The Windows symlink handling may have been fixed in newer speechbrain versions or may be handled differently now.