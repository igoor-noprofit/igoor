# BUGS
- ne pas ouvrir le CLI => tout logger
- FLOW window does not change automatically when recording a new phrase;
if on keyboard mode, it does not go back to predictions 

- FORCE sur la meteo le prompt du flow


- Pyinstaller does not currently work.

# PLUGINS
- prevent errors when deactivating/activating plugins in settings



# FRONTEND

## VUE 
### Global variables
lang and other variables (ex. from onboarding) should be accessible

# DEPLOYMENT
Tools like pip-chill, pipreqs, or pip-autoremove can help identify or remove unnecessary packages.

# IMPROVEMENTS
## HTML
- Move js,css,index_template and index.html inside /public ? beware of /
- Problem: plugins frontends are inside the plugins folders, can you access them?

# FUTURE FEATURES
- Plugins should load/install themselves their needed libraries?
- dynamic plugging/unplugging after (de)activating plugins in settings