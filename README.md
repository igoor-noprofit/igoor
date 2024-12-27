# IGOOR - v0

## REQUIREMENTS

Microsoft Windows.
See requirements.txt

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

User's data folder is automatically created inside userAppDataFolder (usually C:/Users/YourUsername/AppData/).
The application folder (IGOOR_FOLDER) is :

```
C:/Users/YourUsername/AppData/Roaming/igoor/
```

The folder contains a settings.json and a plugins data folder, called "plugins".

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

### Patient documents (RAG, RetrievalAugmentedGeneration, or Static Knowledge Base)

Documents in IGOOR_FOLDER/plugins/rag/medias/ are scanned by the RAG plugin.

Allowed formats:
.pdf
.txt
.md

If the index folder (IGOOR_FOLDER/plugins/rag/faiss_index) does not exist but the medias folder exist, at startup the plugin will create the index by ingesting all the files in the medias folder.

## LAUNCH

```
python main.py
```

## CREATE AN INSTALLER

```
pyinstaller --onefile --add-data "js;js" --add-data "img;img" --add-data "css;css" --add-data "plugins;plugins" --add-data "index.html;." main.py
```

Without console: 

```
pyinstaller main.py --add-data --noconsole index.html:.
```

## EMBEDDING MODELS FOR RAG

Embedding models for RAG are downloaded automatically in their folders inside:

C:\Users\YourUsername\.cache\huggingface\hub


## LOGS
LLM logs are in :

IGOOR_FOLDER/plugins/memory/