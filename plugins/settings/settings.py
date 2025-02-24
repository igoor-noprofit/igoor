from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager

plugin_manager = PluginManager()

class Settings(Baseplugin):
    @hookimpl
    def startup(self):
        self.logger.info("Settings plugin starting up")
        self.is_loaded = True
        
    def get_plugins_by_category(self):
        self.logger.info("Fetching plugins by category in Settings")
        plugins_by_category = plugin_manager.get_plugins_by_category()
        
        # Get current activation states from settings.json
        settings = plugin_manager.settings_manager.get_settings()
        plugins_activation = settings.get("plugins_activation", {})
        self.logger.info(f"Current plugin activation states: {plugins_activation}")
        
        # Update the active status for each plugin
        for category in plugins_by_category:
            for plugin in plugins_by_category[category]:
                plugin_name = plugin["name"]
                # Get activation state from settings.json
                is_active = plugins_activation.get(plugin_name, False)
                self.logger.info(f"Plugin {plugin_name} activation state: {is_active}")
                plugin["active"] = is_active
                
                # Ensure other metadata is included
                if "description" not in plugin:
                    plugin["description"] = plugin_manager.all_plugins.get(plugin_name, {}).get("description", "")
        
        self.logger.info(f"Final plugins by category: {plugins_by_category}")
        return plugins_by_category
        
    def toggle_plugin(self, plugin_name, is_active):
        """Toggle plugin activation state"""
        self.logger.info(f"Toggling plugin {plugin_name} to {is_active}")
        
        # Update settings.json
        settings = plugin_manager.settings_manager.get_settings()
        if "plugins_activation" not in settings:
            settings["plugins_activation"] = {}
        
        settings["plugins_activation"][plugin_name] = is_active
        plugin_manager.settings_manager.save_settings(settings)
        
        # Actually activate/deactivate the plugin
        if is_active:
            plugin_manager.activate_plugin(plugin_name)
        else:
            plugin_manager.deactivate_plugin(plugin_name)
            
        self.logger.info(f"Plugin {plugin_name} toggle complete")
        return True