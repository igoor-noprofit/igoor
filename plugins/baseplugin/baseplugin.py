from settings_manager import SettingsManager
from status_manager import StatusManager
from plugin_manager import hookimpl, PluginManager
import os,sys
class Baseplugin:
    def __init__(self, plugin_name="baseplugin", pm=None):
        print ("__init__ plugin : " + plugin_name)
        self.plugin_name = plugin_name
        if pm is None:
            print ("no plugin manager passed")
            # sys.exit()     
        if isinstance(pm, PluginManager):
            print("Valid PluginManager instance passed.")
            self.pm = pm
        else:
            print("Warning: pm is not a PluginManager instance.")
        
        self.plugin_name = plugin_name
        self.settings_manager = SettingsManager()
        self.status_manager = StatusManager()
        # self.pm = pm
        # Construct the plugin folder path
        self.app_name = os.getenv('IGOOR_APPNAME')  # Get the application name from the environment variable
        self.appdata_path = os.getenv('APPDATA')  # Get the APPDATA path from the environment variable
        self.plugin_folder = os.path.join(self.appdata_path, self.app_name, 'plugins', plugin_name)
        # Create the directory if it doesn't exist
        if not os.path.exists(self.plugin_folder):
            print("CREATING FOLDER ", self.plugin_folder)
            os.makedirs(self.plugin_folder)
        else:
            print("FOLDER EXISTING: " + self.plugin_folder)
    
    '''
    def trigger_hook(self,hook_name,**kwargs):
        print ("BASEPLUGIN TRIGGER HOOK")
        if self.pm:
            try:
                self.pm.trigger_hook(hook_name, msg="Q: " + "prova")
            except TypeError as e:
                print(f"TypeError occurred: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
        else:
            print("Plugin manager is not set.")
            sys.exit()
    '''
        
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
        print("getting settings for ", self.plugin_name)
        return self.settings_manager.get_plugin_settings(self.plugin_name)

    def update_my_settings(self, key: str, value: any):
        """
        Update settings for a specific plugin.
        """
        current_settings = self.get_my_settings()
        current_settings[key] = value
        self.settings_manager.update_plugin_settings(self.plugin_name, current_settings)
        self.settings_manager.save_settings()
        
    def update_status(self, status):
        print(f"Plugin {self.__class__.__name__} received status update: {status}")
        # Implement specific status handling logic here

    def cleanup(self):
        self.status_manager.unregister_observer(self)
        
    def subfolder_exists(self, subfolder_name: str):
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        if not os.path.exists(subfolder_path):
            return False
        return True    
        
    def create_subfolder(self, subfolder_name: str):
        """
        Create a subfolder inside the plugin folder if it doesn't exist.
        Return the full path if created, otherwise return False.
        """
        subfolder_path = os.path.join(self.plugin_folder, subfolder_name)
        try:
            if not os.path.exists(subfolder_path):
                print(f"CREATING SUBFOLDER {subfolder_path}")
                os.makedirs(subfolder_path)
                return subfolder_path
            else:
                print(f"SUBFOLDER ALREADY EXISTS: {subfolder_path}")
                return subfolder_path
        except Exception as e:
            print(f"Failed to create subfolder {subfolder_path}: {e}")
            return False