COMPLETED:
- Removed elevenlabslib dependency and migrated to official ElevenLabs SDK (v2.26.0)
- Fixed the bug where fallback did not work due to unhandled exception in elevenlabslib
- All voice synthesis parameters now properly supported through the official SDK
- Simplified codebase by using only the elevenlabs library 

FEATURE:
- enqueue phrases
- {"stability": 0.2,"similarity_boost": 0.2,"style": 0.2,"use_speaker_boost": true}}'