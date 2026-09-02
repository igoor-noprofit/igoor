# Project Overview

IGOOR is an open-source and free conversational application, controllable also by eye-tracking, designed to provide people with neurodegenerative diseases or paralysis a smooth and natural means of communication.


## Core Architecture

**Plugin-Based System**: IGOOR uses Pluggy for plugin management. Each plugin has:
- Backend: `plugin_name.py` extending `baseplugin.py`
- Frontend: `frontend/plugin_name_component.vue` extending `Baseplugincomponent.js`
- Configuration: `plugin.json` with activation status, category, and database schema
- Settings: `settings.json` for user preferences
- "has_settings": true in plugin.json to allow displaying of plugin settings interface
- Optional `"platforms": ["windows", "macos", "linux"]` in plugin.json restricts the plugin to those OSes (absent = all platforms). Values match `utils.get_platform_key()`. On an incompatible OS the plugin is never loaded, is shown as a disabled "Not available on this platform" card in the Extensions list, and activation is refused — but its `plugins_activation` entry in settings.json is NEVER modified, so user settings stay portable across OSes.
- "user_data" in plugin.json declares the plugin's exportable user data (paths relative to the plugin's APPDATA folder), included automatically by onboarding's export/import. Entries: `{"path": "voices"}` (merge on import, default) or `{"path": "audio", "mode": "replace"}` (wipe local path first, for data that must stay in sync with the DB). Plugins without the key contribute nothing; rag is handled bespoke in data_manager.py because it needs logic beyond copying (embedding-model compatibility). Works for deactivated plugins too (declarations are read from the repo, not from loaded plugins). NEVER hardcode new plugin folders in data_manager.py — declare them here.

**Communication Patterns**:
- Backend-to-backend: Via Pluggy hooks `await self.pm.trigger_hook(hook_name, data)`
- Frontend-to-backend: WebSocket on `ws://localhost:9715/plugin_name` using `sendMsgToBackend(data)`
- REST fallback: FastAPI now exposes REST endpoints (e.g. `/api/plugins/<name>/settings`, `/api/plugins/by-category`, `/api/hooks/<name>`, `/api/app/change-view`) mirroring the former `window.pywebview.api` bridge. Everything is also available at localhost:9714, so ALWAYS test endpoints directly when the app is running with CURL, ex.:
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
- IMPORTANT: After editing `css/app.less`, you MUST recompile it to `css/app.css`, since the running app serves `app.css` and changes to `.less` are not picked up automatically. The project has no build watcher or `package.json`/eslint tooling — run the compiler manually from the repo root:
  ```
  npx --yes less css/app.less css/app.css
  ```
  (This fetches the `less` npm package on first run via `npx`, no global install needed. Commit BOTH `css/app.less` and `css/app.css` so they stay in sync.)
- Component methods prefixed with `$_` to avoid global conflicts
- Dynamic component loading via httpVueLoader
- When choosing colors,always start from predefined colors in /css/app.less

**Interface guidelines**: Since the interface is for users who have physical conditions,buttons should generally be big.
Also, MINIMIZE the number of clicks needed for each action.

**Icons**: Use outline / line icons only — never filled (solid) icons. The app ships only `css/phosphor-2.1.1-light.css`, so use the `ph-light` weight (e.g. `<i class="ph-light ph-play"></i>`); for SVGs, use the line-style set under `/img/icons/src/` (e.g. `microphone.svg`). Filled icons (`ph-fill`, or solid glyphs) clash with the UI and must not be used.

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
│       ├── plugin_name_fr_FR.json  # Translations - use t('string') method to provide translatable strings - IMPORTANT: ENGLISH has no translation file, it's default - IMPORTANT: when you change/add/remove a t() string, update the matching key in EVERY locale file (e.g. fr_FR, it_IT); leaving one out of sync silently falls back to English
│       └── prompts.py              # AI prompts
├── plugin.json             # Plugin config & DB schema
└── settings.json          # Default settings
```

**Critical Plugins**:
- `onboarding`: User prefs and AI settings
- `asrjs`: Speech recognition (Sherpa-ONNX local, Whisper via Groq and Voxtral via Mistral, wakeword detection)
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
- PyInstaller with custom hooks
- Fast build: `create_exe_fast.bat` (5-7 min)
- Full build: `create_exe.bat` (8-10 min)
- PyInstaller spec file: `igoor.spec.txt` is the source-of-truth committed to git. The `.spec` file used at build time is generated from it. Any changes to hiddenimports, datas, or excludes must be made in `igoor.spec.txt`.
- **Important**: Plugins are loaded dynamically, so PyInstaller can't auto-detect their imports. If a plugin uses a package not imported in `main.py`, add it to `hiddenimports` in `igoor.spec.txt`.

**Python Version**: Tested on 3.10.6 only

## Testing Python syntax
If you modify a python file, ALWAYS test syntax with:

python -m scriptname.py

before telling me you finished.

## Testing .js/.vue syntax
After you finish modifying .js/.vue files:

1. List exactly which files you changed
2. Run the project's lint command on those files only (npm run lint -- <files>)
3. Run type checker (tsc --noEmit or vue-tsc --noEmit)
4. Show me any errors/warnings
5. If there are errors → propose fixes and apply them in a follow-up edit
6. Only tell me "ready" when lint + types are clean

## Accesing and testing the frontend
To test the frontend verify if IGOOR is running in Python. 
If not: 
/venv/scripts/Activate
python main.py
THEN,leverage whatever MCP tool for browsing is available to browse @ http://127.0.0.1:9714/ (use Playwright if available)
In the frontend, you have to click on the settings-gear top right in the header to access all the extensions. 
Once there,you have to click on the extensions tab,the plugin category etc.

## Checking the libraries documentation
ALWAYS use Context7 MCP to access the documentation corresponding to the installed python libraries.

Behavioral guidelines to reduce common LLM coding mistakes:

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.