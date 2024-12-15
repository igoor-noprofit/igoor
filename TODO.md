# PLUGINS
- prevent errors when deactivating/activating plugins in settings


unify methods : 
_trigger_plugin_hook
trigger_hook

# HTML
- Move js,css,index_template and index.html inside /public ? beware of /
- Problem: plugins frontends are inside the plugins folders, can you access them?

# DEPLOYMENT
Tools like pip-chill, pipreqs, or pip-autoremove can help identify or remove unnecessary packages.

FUTURE FEATURES
- Plugins should load/install themselves their needed libraries?
- dynamic plugging/unplugging after (de)activating plugins in settings