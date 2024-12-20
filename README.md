# IGOOR - v0

## REQUIREMENTS

## SETUP VIRTUAL ENVIRONMENT
```
python -m venv venv
venv\scripts\activate
```

## INSTALLATION
```
pip install -r requirements.txt
```

To update requirements: 
```
pip freeze > requirements.txt
```

## USER'S DATA FOLDER

User's data folder is automatically created inside userAppDataFolder (usually C:/Users/username/AppData/).
IGOOR_FOLDER is :

```
C:/Users/username/AppData/Roaming/igoor/
```

The folder contains a settings.json and a plugins data folder, called plugins.

### NOTES ABOUT PLUGINS

Plugins are currently activated by manually setting the corresponding variable in the plugin.json file inside 

/plugins/plugin_name/plugins.json

Example: /plugins/meteo/plugin.json :

```
{
    "active": true,
```

#### AUTOMATIC SPEECH RECOGNITION WITH VOSK

Vosk is a local ASR plugin.
It expects a model downloaded manually from this page in your language: 

https://alphacephei.com/vosk/models

And placed in 

IGOOR_FOLDER/plugins/asrvosk/models/language/model_size

Language and model size are set in the plugin's json, example:

```
"asrvosk":{
            "lang":"fr_FR",
            "wakeword":"Igor",
            "model_size":"small"
        }
```

In this case the final path is :

IGOOR_FOLDER/plugins/asrvosk/models/language/model_size

### Patient documents (RAG, RetrievalAugmentedGeneration)

Documents in IGOOR_FOLDER/plugins/rag/medias/ are scanned by the RAG plugin.

Allowed formats:
.pdf
.txt
.md

If the index folder (IGOOR_FOLDER/plugins/rag/faiss_index) does not exist but the medias folder exist, at startup the plugin will create the index

## CREATE AN INSTALLER

```
pyinstaller main.py --add-data "css;css" --add-data "img;img" --add-data "js;js" --add-data "locales;locales" --add-data index.html:.
```

Without console: 

```
pyinstaller main.py --add-data --noconsole index.html:.
```


## LAUNCH

```
python main.py
```

## LOGS
LLM logs are in :

IGOOR_FOLDER/plugins/memory/