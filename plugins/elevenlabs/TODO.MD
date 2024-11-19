BUG:
- generate_audio is slower and doesn't support onplaybackend, which is necessary to avoid ASR on the phrase pronounced by Elevenlabs
- stream_audio is faster and supports onplaybackend, but has buffer errors 
