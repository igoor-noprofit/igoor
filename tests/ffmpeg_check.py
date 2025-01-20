import torchaudio

# Check available backends
print("Available torchaudio backends:", torchaudio.list_audio_backends())

# Try to use ffmpeg backend
try:
    torchaudio.set_audio_backend("ffmpeg")
    print("FFmpeg backend successfully loaded")
except Exception as e:
    print("FFmpeg backend not available:", e)