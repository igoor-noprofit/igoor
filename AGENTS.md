# Project Overview

IGOOR is an open-source and free conversational application, controllable also by eye-tracking, designed to provide people with neurodegenerative diseases or paralysis a smooth and natural means of communication.

## Core Architecture

**Plugin-Based System**: IGOOR uses Pluggy for plugin management. Each plugin has:
- Backend: `plugin_name.py` extending `baseplugin.py`
- Frontend: `frontend/plugin_name_component.vue` extending `Baseplugincomponent.js`
- Configuration: `plugin.json` with activation status, category, and database schema
- Settings: `settings.json` for user preferences
- "has_settings": true in plugin.json to allow displaying of plugin settings interface

**Communication Patterns**:
- Backend-to-backend: Via Pluggy hooks `await self.pm.trigger_hook(hook_name, data)`
- Frontend-to-backend: WebSocket on `ws://localhost:9715/plugin_name` using `sendMsgToBackend(data)`
- REST fallback: FastAPI now exposes REST endpoints (e.g. `/api/plugins/<name>/settings`, `/api/plugins/by-category`, `/api/hooks/<name>`, `/api/app/change-view`) mirroring the former `window.pywebview.api` bridge. Everything is also available at localhost:9714, so you can test directly when the app is running CURL, for ex. at:
http://localhost:9714/api/plugins/asrjs/settings
- Frontend readiness: `window.ensureBackendApi()` lazily resolves a `BackendApi` wrapper that chooses between the PyWebView bridge and REST calls; the root app calls `readypy()` automatically when no bridge is detected
- Plugins can use callPluginRestEndpoint to call the API endpoints (own plugin and other plugins; supports GET and POST)

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
- IMPORTANT: the only files you will find in APPDATA subfolder (/web/) are app.js and app.vue
- IMPORTANT: NEVER edit `app.js` or `app.vue` directly, nor even in the APPDATA_FOLDER (they are just builds): ALWAYS edit `app_template.js` and `app_template.vue` instead
- IMPORTANT: NEVER edit `css/app.css`, ALWAYS edit `css/app.less` instead
- Component methods prefixed with `$_` to avoid global conflicts
- Dynamic component loading via httpVueLoader
- When choosing colors,always start from predefined colors in /css/app.less

**Interface guidelines**: Since the interface is for users who have physical conditions,buttons should generally be big.

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
│       ├── plugin_name_fr_FR.json  # Translations - use t('string') method to provide translatable strings - IMPORTANT: ENGLISH has no translation file, it's default
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
- Plugins data: `plugins/` subdirectory, containing all dynamic data from plugins. The app can download models in user data folders (ex. HuggingFace) but CANNOT create folders inside the app root,otherwise this will give problems when running as executable.
- Logs: `logs/` (daily rotation)
- LLM calls: `llm_invocations/` (JSON with prompts/responses)

**External Dependencies**:
- WebView2 Runtime for display
- FFmpeg for Speechify TTS (must be in PATH)
- Groq API for AI inference
- Embedding models: 1.15GB from HuggingFace

## Development Notes


**Build Process**: 
- PyInstaller with custom webrtcvad hook
- Fast build: `create_exe_fast.bat` (5-7 min)
- Full build: `create_exe.bat` (8-10 min)

**Python Version**: Tested on 3.10.6 only

## Accesing and testing the frontend
To test the frontend verify if IGOOR is running in Python. 
If not: 
/venv/scripts/Activate
python main.py
THEN,leverage whatever MCP tool for browsing is available to browse @ http://127.0.0.1:9714/ (use Playwright if available)
In the frontend, you have to click on the settings-gear top right in the header to access to access all the extensions. 
Once there,you have to click on the extensions tab,the plugin category etc.

## Checking the libraries documentation
ALWAYS use Context7 MCP to access the documentation corresponding to the installed python libraries.