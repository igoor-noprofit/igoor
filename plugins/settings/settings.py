from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager

plugin_manager = PluginManager()

class Settings(Baseplugin):
    @hookimpl
    def startup(self):
        print("STARTUPSELF")
        
    def get_plugins_by_category(self):
        print("Fetching plugins by category in Settings")
        return plugin_manager.get_plugins_by_category()