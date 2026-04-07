[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

# IGOOR

**IGOOR is an open-source and free (AGPLv3) conversational application based on AI, designed to provide people with ALS/MND diseases a smooth and natural means of communication.** 
Its interface makes it easy-to-use also via eye-tracking device.

<a href="https://igoor.org" target="_blank"><img src="./img/logo_fb.png" alt="logo IGOOR" width="400"></a>

Take a look at the <a href="https://igoor.org/en">IGOOR website</a> for further infos about our core principles, values and software roadmap.

IGOOR is developed by <a href="https://igoor.org" target="_blank">IGOOR not for profit organisation</a>, in partnership with <a href="https://www.arsla.org/">ARSLA</a>, based on an <a href="https://vimeo.com/980377339?fl=pl&fe=vl" target="_blank">original idea by Igor Novitzki</a>.
The <a href="https://www.aphp.fr/hopitaux/hendaye" target="_blank">Hôpital Marin d'Hendaye</a> is also partnering to support the evaluation phase of the tool.
<p>
<a href="https://arsla.org" target="_blank"><img src="https://igoor.org/wp-content/uploads/2025/06/arsla-logo-principal-png-1536x1086-1.png" alt="logo ARSLA" width="250"></a></p>

## DOCUMENTATION

Documentation is ongoing. We strive to keep it up to date with latest functionalities, and to translate tutorials from French.

- English : [IGOOR docs](https://igoor-noprofit.github.io/docs/)
- French : [Documentation IGOOR](https://igoor-noprofit.github.io/docs/fr/)

## REQUIREMENTS

- **Windows 10/11** (PC or tablet)
- Minimum resolution: 1280,960
- Recommended resolution: 1920x1080 or more
- **Internet connection (preferably optic fiber or ADSL)**
- A Groq API key

### Microsoft © Edge WebView2 Runtime

This application currently uses Microsoft Edge WebView2 Runtime to display a browser-like window.

You can download it here:

https://developer.microsoft.com/en-us/microsoft-edge/webview2?form=MA13LH#download

**NOTE: IGOOR installers sistematically include the runtime.**
Download latest executable from:

https://github.com/igoor-noprofit/igoor/releases/download/latest/IGOOR.exe


Microsoft Edge WebView2 Runtime is © Microsoft Corporation.

### AI INFERENCE PROVIDER

The only AI inference provider currently meeting our requirements of speed, privacy, quality, support of opensource models and availability of both ASR/LLM inference is Groq.
Signup for a FREE-tier access to Groq's API here:

https://console.groq.com/login

For production use, you will need a developer tier self-serve (Pay per Token) access, 
or you'll rapidly incur in rate limits errors.

We plan on supporting other providers soon, as well as local models.

### DISK SPACE

In the user's data folder, big ASR models (like Vosk) take around 2.3Gb, plus 1.4 for the zip file.

The embedding model from HuggingFace currently requires 1.15Gb on disk.

The app should take less than 3Gb.

### FFMPEG

As of now, TTS plugin for Speechify requires ffmpeg, and that the path to ffmpeg\bin folder be included in the system PATH environment variable.

**NOTE: IGOOR installers include ffmpeg and automatically set the env variable.**

### PYTHON

See requirements.txt for a list of Python libraries needed.

## INSTALLATION

### PYTHON VERSION

Currently tested on **Python 3.10.6**. Download it from here: 

https://www.python.org/downloads/release/python-3106/

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

User's data folder is automatically created inside userAppDataFolder (on Windows is usually C:/Users/YourUsername/AppData/).
The application folder (IGOOR_FOLDER) on Win is :

```
C:/Users/YourUsername/AppData/Roaming/igoor/
```

The folder contains a settings.json and a plugins data folder, called "plugins".

### EMBEDDING MODELS FOR RAG

Embedding models for RAG are downloaded automatically in their folders.
On Win, this is at:

```
C:\Users\YourUsername\.cache\huggingface\hub
```

Other models can be saved in this folder.

## LAUNCH

*EXPERIMENTAL*: You can now launch IGOOR in CLI mode (IGOOR_CLI=True in .env), which is a headless mode you can access with the browser at http://127.0.0.1:9714/ (via FastAPI). As of now this is mostly for easier debug with VueDevTools, agents etc.

Default mode is inside pywebview webedge window (IGOOR_CLI=False).
PLEASE NOTE: Opening inside both pywebview AND external browser will yield unwantend sync between the two clients.

#### AUTOMATIC SPEECH RECOGNITION WITH VOSK

Vosk is a local ASR (Automatic Speech Recognition) plugin.
It automatically downloads a model from this page in the user's language (default "fr"): 

https://alphacephei.com/vosk/models

And places it in 

IGOOR_FOLDER/plugins/asrvosk/models/language/model_size

Language and model size are set in the global settings file, example:

```
other plugins...
"asrvosk": {
    "lang": "fr_FR",
    "wakeword": "Igor",
    "model_size": "small",
    "continuous": false,
    "min_confidence": 0.7
}
...other plugins
```

In this case the final path is :

IGOOR_FOLDER/plugins/asrvosk/models/language/model_size

NOTE: Because of its high WER compared to Whisper and Voxtral, we recommend using Vosk only if audio privacy is paramount.
VOSK will be probably deprecated in favor of another ASR model.

# PYWEBVIEW: cache problems after updating version
After updating, if you have problems with cache, but only in Pywebview window (as opposed to localhost:9714), delete this folder to delete Pywebview cache:

```
C:\Users\<user_name>\AppData\Roaming\pywebview\EBWebView
```

## CREATE AN EXECUTABLE

### REQUIREMENTS 

First of all, upgrade pyinstaller in your venv:

```
pip install --upgrade pyinstaller
```

and hooks-contrib

```
pip install --upgrade pyinstaller-hooks-contrib
```

### WEBRTCVAD-WHEELS

Modify the hook in the virtual environment folder:

\venv\lib\site-packages\_pyinstaller_hooks_contrib\stdhooks\hook-webrtcvad.py

Replace code with this code:
```
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('webrtcvad-wheels')
```

### CREATE THE EXECUTABLE / INNOSETUP 

In powershell (VS Code terminal):

```
venv\scripts\Activate
.\create_installable.bat
```

It will ask you if you want to:

1) Create only the exe file
2) Create exe file AND installer
3) Create both AND push to GitHub release
4) Push to GitHub release only (exe and installer already exist)
    THIS ONE IS REQUIRES github token
5) Create only the installer (skip exe build)

In a CMD window, launch /dist/igoor/igoor.exe 
(so you can see the logs if there's any error)

## IGOOR LOGS
Daily logs are in:

```
IGOOR_FOLDER/logs/
```

Separate llm_invocations contain a JSON of all LLM calls, with prompt/answer and reasoning (where applicable)

## License

IGOOR is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Copyright (C) 2025-2026 Carlo Giordano, Igor Novitzki and the IGOOR not-for-profit organization (https://igoor.org)

IGOOR is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with IGOOR.  If not, see <https://www.gnu.org/licenses/>.

## ADDING A LANGUAGE

### REQUIREMENTS
For each plugin, check if the language is supported. Start by Vosk and Whisper models.
For each LLM, check if the language is supported too.
For TTS, check if the external model supports the language (Eleven Labs, Speechify etc.)

### PLUGINS

### ASR KNOWN BUGS
New languages may require new filters to be applied (see known issues 1).

## KNOWN ISSUES ##
1) ASR models can interpret silence or very low, inaudible sounds as speech and return texts like "Thank you" instead of empty texts. This depends on the ASR models, not the IGOOR app.
Whisper and Voxtral models have a known bug that can convert silences or very low, inaudible sounds, to specific strings never uttered by the user (ex. "Sous-titrage ST' 501"). These are cleaned by the function "clean_whisper_silence" in plugins/asrwhisper.py (added in 0.1.3.5). 
