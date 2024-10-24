from settings_manager import SettingsManager
from plugin_manager import hookimpl
import os 

class Baseplugin:
    def __init__(self, plugin_name="baseplugin"):
        self.plugin_name = plugin_name
        self.settings_manager = SettingsManager()
        # Construct the plugin folder path
        app_name = os.getenv('IGOOR_APPNAME')  # Get the application name from the environment variable
        appdata_path = os.getenv('APPDATA')  # Get the APPDATA path from the environment variable
        self.plugin_folder = os.path.join(appdata_path, app_name, 'plugins', plugin_name)
        
        # Create the directory if it doesn't exist
        if not os.path.exists(self.plugin_folder):
            os.makedirs(self.plugin_folder)

        print(f"Plugin folder set to: {self.plugin_folder}")
        
    @hookimpl
    def get_frontend_components(self):
        vue_component = self.plugin_name + "_component.vue"
        print("loading vue component ",vue_component)
        return [
            {
                "vue": vue_component
            }
        ]

    def get_my_settings(self) -> dict:
        """
        Retrieve settings specific to the plugin.
        """
        return self.settings_manager.get_plugin_settings(self.plugin_name)

    def update_my_settings(self, key: str, value: any):
        """
        Update settings for a specific plugin.
        """
        current_settings = self.get_my_settings()
        current_settings[key] = value
        self.settings_manager.update_plugin_settings(self.plugin_name, current_settings)
        self.settings_manager.save_settings()