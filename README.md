![Image](img/logo_fb.png)

# IGOOR

IGOOR is an open-source and free conversational application, controllable by eye-tracking, designed to provide people with neurodegenerative diseases or paralysis a smooth and natural means of communication.


## Notice of Development, Confidentiality, and Contribution Terms

**This project is currently under private development. While the final version of the software will be released as free/libre under the GPLv3 License, the current codebase is not yet public and is subject to strict confidentiality.**

All collaborators and contributors are reminded that:

1. Sharing Prohibited: The code, documentation, and any associated materials must not be shared, distributed, or disclosed to anyone outside of the development team without prior written permission.
2. Access Restriction: Access to this repository is granted solely for the purpose of contributing to the project's private development phase.
3. Contribution Licensing: By contributing to this project, you agree that all contributions you make will be licensed under the GPLv3 License upon the software's public release.

Failure to comply with these terms may result in immediate removal from the project and other appropriate actions.

Thank you for your understanding and cooperation in ensuring the successful development of this software.

## REQUIREMENTS

**Microsoft Windows. Tested on Windows 11.**

See requirements.txt for a list of Python libraries needed.

## INSTALLATION

### PYTHON VERSION

Currently tested on **Python 3.10.6**

### UPGRADE PIP
```
python -m pip install --upgrade pip
```

### SETUP VIRTUAL ENVIRONMENT
```
python -m venv venv
venv\scripts\activate
```

### INSTALL LIBRARIES
```
pip install -r requirements.txt
```

### ENV
Rename environment variables:

```
rename .env-example .env
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

Vosk is a local ASR (Automatic Speech Recognition) plugin.
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

### Static Knowledge Base from patient documents (RAG, RetrievalAugmentedGeneration)

Documents in IGOOR_FOLDER/plugins/rag/medias/ are scanned by the RAG plugin.

Allowed formats:
.pdf
.txt
.md

If the index folder (IGOOR_FOLDER/plugins/rag/faiss_index) does not exist but the medias folder exist, at startup the plugin will create the index by ingesting all the files in the medias folder.

### EMBEDDING MODELS FOR RAG

Embedding models for RAG are downloaded automatically in their folders inside:

```
C:\Users\YourUsername\.cache\huggingface\hub
```

## LAUNCH

```
python main.py
```

This launches in a resizable window, with the browser's debug console opened and the python CLI visible.

Use:

```
igoor.bat
```

to open a fullscreen window, without CLI and debug console.

## CREATE AN INSTALLER

The pyinstaller uses igoor.spec 

```
pyinstaller igoor.spec --noconfirm
```
To update requirements: 
```
pip freeze > requirements.txt
```



## LOGS
LLM logs are in the correspondent plugin's folder, ex. :

```
IGOOR_FOLDER/plugins/memory/
```


