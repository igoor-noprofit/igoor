# Placeholder for wakeword models

# This directory will contain the ONnx models for wakeword detection.
# When you models are available here, they will be used.
# 
# Default models (language-specific):
# - hey_igor_en.onnx - English: "Hey Igor"
# - hey_igor_fr.onnx - French: "Hé Igor"
# 
# The custom models should be uploaded to the APPDATA folder:
# via the settings UI
# 
# Dependencies:
# - openwakeword Python package
# - numpy
# - fastapi for UploadFile, File, HTTPException
# - APIRouter
