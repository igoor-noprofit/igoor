# IGOOR - v0

## SETUP

## INSTALL PACKAGES
```
pip install -r requirements.txt
```

To update reqs: 
```
pipreqs --force
```

## SETUP VIRTUAL ENVIRONMENT
```
python -m venv venv
venv\scripts\activate
```
## USER FOLDER

User folder is automatically created inside userAppDataFolder (usually C:/Users/username/AppData/).
Final folder is :

C:/Users/username/AppData/Roaming/igoor/

The folder contains a settings.json and a plugins data folder called plugins.

### NOTES ABOUT PLUGINS

Plugins are currently activated by manually setting the corresponding variable in the plugin.json file inside /plugins/plugin_name/plugins.json

Example:
```
{
    "active": true,
```


#### Patient documents
Documents in userAppDataFolder/plugins/rag/medias/ are scanned by the RAG plugin.

Allowed formats:
.pdf
.txt
.md

If the index folder (userAppDataFolder/plugins/rag/index) does not exist but the medias folder exist, 
at startup the plugin will create the index


## LAUNCH

python main.py

### FOLDER STRUCTURE


