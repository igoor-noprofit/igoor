## Fix speechbrain.inference.speaker Import Error (Version 0.5.15)

**Problem**: `speechbrain.inference.speaker` module doesn't exist in speechbrain 0.5.15. The correct class is `SpeakerRecognition` from `speechbrain.pretrained.interfaces`.

**Solution**: Update the import in `plugins/speakerid/speechbrain.py` to use the correct module and class for speechbrain 0.5.15.

**Changes**:
- File: `C:\AIKU\experiments\igoor\plugins\speakerid\speechbrain.py`
- Line 23: Change from `speechbrain.inference.speaker import EncoderClassifier` 
  to `speechbrain.pretrained.interfaces import SpeakerRecognition`
- Update the model initialization to use `SpeakerRecognition.from_hparams()` instead of `EncoderClassifier.from_hparams()`
- The class will work similarly but using the correct import path for version 0.5.15

The `SpeakerRecognition` class in `speechbrain.pretrained.interfaces` provides the same speaker recognition functionality and `from_hparams()` method.