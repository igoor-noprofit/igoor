IGOOR is a free/libre Python desktop conversational app for Windows 10/11, to provide people with neurodegenerative diseases a smooth and natural means of communication.

BACKEND
Based on Pluggy to handle plugins, Pywebview to display the main Vue app and its frontend.
- plugin_manager.py is a singleton loading and activating the different plugins.Each plugin has a JSON file like this :
{
    "active": true,
    "category": "context",
    ...
    
- websocket_server.py allows communications between plugins' backend and frontend
- context_manager.py shares info about the context between main app and plugins (conversation,datetime, geoloc, weather etc.)
- settings_manager.py is a singleton that loads and writes to a simple JSON user settings file located in the user APPDATA folder in Windows. Example:
{
"plugins": {
        "elevenlabs": {
            "voice_id": "...",
            "api_key": "..."
        },
}
- plugin.json file contains the db schema too (where needed)
- llm_manager.py handles calls to external LLMs,supporting JSON answers via pydantic and using langchain
- status_manager.py is a singleton sharing infos with the plugins about the app(status,etc.)
- js_api.py contains the API to connect python and javascript through pywebview
- db_manager.py handles the local sqlite3 db. Each plugin can access it via self.db

MOST IMPORTANT PLUGINS OVERVIEW
- onboarding:handles basic user preferences and AI settings
- asrvosk/asrshiper:speech recognition via Vosk (supports continuous listening or on click listening) or Whisper on Groq
- autocomplete:based on LLM predictions
- conversation:handles current conversation
- daily:handles user's daily needs
- flow:leverages ASR to create answer predictions
- rag:indexes ingested documents in FAISS vectore and sqlite db
- memory:handles long-term and short term memory additions in FAISS db
- elevenlabs/speechify:TTS

FRONTEND
Main Vue app is js/app_template.vue. App_template.js contains Vue components dynamically loaded with httpVueLoader.
Each plugin has a frontend folder with a corresponding Vue component. Vue components are based on js/Baseplugincomponent.js
IMPORTANT: NEVER EDIT DIRECTLY app.js or app.vue, edit app_template.js or app_template.vue instead.
I don't use bundlers for the Vue 3 app,I use httpVueLoader to load SFC.

VUE COMPONENTS
Syntax for internal methods is $_funcname,in order to avoid confusion with global methods.

SIMPLIFIED FOLDER STRUCTURE
├── main.py (main app)
├── context_manager.py
├── css (frontend css)
├── img (frontend img)
├── js (main Vue app, )
│   ├── app_template.vue (main Vue app)
│   ├── Baseplugincomponent (frontend version of Baseplugin)
├── llm_manager.py
├── plugin_manager.py
├── plugins
│   ├── daily
│   │   ├── daily.py                    (the plugin backend, based on baseplugin.py)
│   │   ├── locales
│   │   │   ├── fr_FR
│   │   │   │   ├── daily_fr_FR.json    (translations for backend/frontend: use self.get_my_translations)
│   │   │   │   ├── prompts.py          (dict of AI prompts for the plugin, where needed: : use self.get_my_prompts)
│   │   │   ├── ...
│   │   ├── frontend
│   │   │   ├── daily_component.vue     (the plugin frontend)
│   │   │   └── daily_settings.vue      (the plugin settings frontend)
│   │   ├── plugin.json
│   │   └── settings.json
│   ├── other plugin...

COMMUNICATION BETWEEN PLUGIN BACKENDS
This happens via the triggers provided by Pluggy, example : 

await self.pm.trigger_hook(hook_name="asr_msg", msg="Q: " + following_text)	

COMMUNICATION BETWEEN PLUGIN FRONTENDS AND BACKENDS
Method: 

sendMsgToBackend(data)

Via a websocket on port 

ws://localhost:9715/plugin_name (ex. meteo)

where both frontend and backend are listening by default on creation.

Vue component frontend communicates its 

{“status”: “ready”}

to the backend, which in turn can start sending updates to the frontend. 
Everything should be passed in JSON mode.