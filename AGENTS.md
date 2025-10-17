# Project Overview

IGOOR is an open-source and free conversational application, controllable also by eye-tracking, designed to provide people with neurodegenerative diseases or paralysis a smooth and natural means of communication.

## Core Architecture

**Plugin-Based System**: IGOOR uses Pluggy for plugin management. Each plugin has:
- Backend: `plugin_name.py` extending `baseplugin.py`
- Frontend: `frontend/plugin_name_component.vue` extending `Baseplugincomponent.js`
- Configuration: `plugin.json` with activation status, category, and database schema
- Settings: `settings.json` for user preferences

**Communication Patterns**:
- Backend-to-backend: Via Pluggy hooks `await self.pm.trigger_hook(hook_name, data)`
- Frontend-to-backend: WebSocket on `ws://localhost:9715/plugin_name` using `sendMsgToBackend(data)`
- REST fallback: FastAPI now exposes REST endpoints (e.g. `/api/plugins/<name>/settings`, `/api/plugins/by-category`, `/api/hooks/<name>`, `/api/app/change-view`) mirroring the former `window.pywebview.api` bridge.
- Frontend readiness: `window.ensureBackendApi()` lazily resolves a `BackendApi` wrapper that chooses between the PyWebView bridge and REST calls; the root app calls `readypy()` automatically when no bridge is detected.

## Key Managers

**Singleton Pattern**: All managers are singletons accessible via `self.manager_name`
- `plugin_manager.py`: Loads/activates plugins via JSON config
- `context_manager.py`: Shares conversation, datetime, geoloc, weather
- `settings_manager.py`: Handles user settings in APPDATA folder
- `llm_manager.py`: External LLM calls with JSON/pydantic support via langchain
- `status_manager.py`: App status sharing with plugins
- `db_manager.py`: SQLite3 access for plugins via `self.db`

## Frontend Rules

**Vue 3 Without Bundlers**: Uses httpVueLoader for SFC loading
- NEVER edit `app.js` or `app.vue` directly, nor even in the APPDATA_FOLDER (they are just builds): ALWAYS edit `app_template.js` and `app_template.vue` 
- Component methods prefixed with `$_` to avoid global conflicts
- Dynamic component loading via httpVueLoader
- When choosing colors,always start from predefined colors in /css/app.less

## Plugin Development

**File Structure**:
```
plugin_name/
├── plugin_name.py          # Backend logic
├── frontend/
│   ├── plugin_name_component.vue    # Main UI
│   └── plugin_name_settings.vue     # Settings UI
├── locales/
│   └── fr_FR/
│       ├── plugin_name_fr_FR.json  # Translations
│       └── prompts.py              # AI prompts
├── plugin.json             # Plugin config & DB schema
└── settings.json          # Default settings
```

**Critical Plugins**:
- `onboarding`: User prefs and AI settings
- `asrvosk/asrwhisper`: Speech recognition (Vosk local, Whisper via Groq and Voxtral via Mistral)
- `elevenlabs/speechify`: TTS integration
- `conversation`: Current conversation handling
- `memory`: FAISS-based long/short-term memory
- `rag`: Document indexing in FAISS + SQLite

## Environment & Data

**User Data Folder**: `C:/Users/Username/AppData/Roaming/igoor/`
- Settings: `settings.json`
- Plugins data: `plugins/` subdirectory
- Logs: `logs/` (daily rotation)
- LLM calls: `llm_invocations/` (JSON with prompts/responses)

**External Dependencies**:
- WebView2 Runtime for display
- FFmpeg for Speechify TTS (must be in PATH)
- Groq API for AI inference
- Vosk models: 2.3GB downloaded to user folder
- Embedding models: 1.15GB from HuggingFace

## Development Notes

**ASR Silence Bug**: Whisper/Voxtral may interpret silence as "Sous-titrage ST' 501" - filtered via `clean_whisper_silence()`

**Build Process**: 
- PyInstaller with custom webrtcvad hook
- Fast build: `create_exe_fast.bat` (5-7 min)
- Full build: `create_exe.bat` (8-10 min)

**Python Version**: Tested on 3.10.6 only