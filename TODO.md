# PLUGINS

- Plugins should load/install themselves their needed libraries?
- plugin.json should contain at least
    title (gettext string?)
- dynamic plugging/unplugging after (de)activating plugins in settings


Tools like pip-chill, pipreqs, or pip-autoremove can help identify or remove unnecessary packages.

- plugin_manager.py :
unify methods : 
_trigger_plugin_hook
trigger_hook

# HTML
- Move js,css,index_template and index.html inside /public ? beware of /
- Problem: plugins frontends are inside the plugins folders