# PLUGINS

- Plugins should load/install themselves their needed libraries?
- plugin.json should contain at least
    title (gettext string?)
- dynamic plugging/unplugging after (de)activating plugins in settings


Tools like pip-chill, pipreqs, or pip-autoremove can help identify or remove unnecessary packages.

## plugin_manager.py :

Exploit results from hooks :
    @pluggy.HookspecMarker(app_name)
        async def speak(self, message):
            # Gather all results from the async hook implementations
            results = await asyncio.gather(
                *self.plugin_manager.hook.speak(message=message)
            )
            return results  # Return the list of results

unify methods : 
_trigger_plugin_hook
trigger_hook

# HTML
- Move js,css,index_template and index.html inside /public ? beware of /
- Problem: plugins frontends are inside the plugins folders