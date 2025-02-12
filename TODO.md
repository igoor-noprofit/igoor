# BUGS
Pyinstaller does not currently work.

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