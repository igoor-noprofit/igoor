import importlib.util
import os, sys
import json
import pluggy
from settings_manager import SettingsManager
from dotenv import load_dotenv
load_dotenv()
import os
from typing import Any
from status_manager import StatusManager


IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
app_name = os.getenv("IGOOR_APPNAME")
hookspec = pluggy.HookspecMarker(app_name)
hookimpl = pluggy.HookimplMarker(app_name)

class MyAppSpec:
    @pluggy.HookspecMarker(app_name)
    def get_frontend_components(self):
        """Hook for plugins to provide frontend components"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def startup(self):
        """Hook for plugins to perform startup activities"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def speak(self,message):
        self.plugin_manager.hook.speak(message=message)
        pass
    
    @pluggy.HookspecMarker(app_name)
    def process_wake_word(self, text):
        """Hook for processing wake word detected text"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def activate(self):
        """Hook for plugins to perform actions upon activation."""
        pass

    @pluggy.HookspecMarker(app_name)
    def deactivate(self):
        """Hook for plugins to perform actions upon deactivation."""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def send_prompt(self, prompt: str) -> None:
        """Hook for plugins to perform actions when sending prompt"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def speaker_msg(self, msg: str) -> None:
        """Hook for plugins to perform actions when speaker has said something via ASR"""
        pass
        
class PluginManager:
    def __init__(self):
        self.status_manager = StatusManager()
        self.plugins = []
        self.plugin_manager = pluggy.PluginManager(app_name)
        self.plugin_manager.add_hookspecs(MyAppSpec)

        # Load global settings
        self.settings_manager = SettingsManager()

        # Load plugins dynamically from the plugins/ directory based on activation state
        self.load_plugins()
        self.startup_plugins()
        
    def trigger_hook(self, hook_name, **kwargs):
        print("Hook triggered")
        """Generic method to trigger any hook by name."""
        hook = getattr(self.plugin_manager.hook, hook_name, None)
        if hook:
            results = hook(**kwargs)
            for result in results:
                print(result)
        else:
            print(f"Hook '{hook_name}' not found.")
        
    def is_active(self, plugin_name):
        is_active = self.all_plugins.get(plugin_name, {}).get("active", False)
        print(f"{plugin_name} is {'active' if is_active else 'NOT active'}")
        return is_active

    def load_plugins(self):
        print("Loading plugins")
        plugin_folder = "plugins"
        self.all_plugins = self.get_all_plugins()
        for plugin_name in os.listdir(plugin_folder):
            plugin_path = os.path.join(plugin_folder, plugin_name)
            if os.path.isdir(plugin_path) and self.is_active(plugin_name):
                try:
                    plugin_module = importlib.import_module(f"plugins.{plugin_name}.{plugin_name}")
                    plugin_instance = getattr(plugin_module, f"{plugin_name.capitalize()}",self)()
                    self.plugins.append(plugin_instance)
                    self.plugin_manager.register(plugin_instance)
                    self.status_manager.register_observer(plugin_instance)
                except Exception as e:
                    print(f"Error loading plugin '{plugin_name}': {e}")
                    if IGOOR_DEBUG:
                        sys.exit()

    def get_all_plugins(self):
        """Gathers activation status and other metadata for all plugins."""
        plugin_folder = "plugins"
        plugins_metadata = {}

        for plugin_name in os.listdir(plugin_folder):
            plugin_path = os.path.join(plugin_folder, plugin_name)
            metadata_file = os.path.join(plugin_path, 'plugin.json')
            if os.path.isdir(plugin_path) and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        plugins_metadata[plugin_name] = metadata
                except (OSError, json.JSONDecodeError) as e:
                    print(f"Error loading metadata for plugin '{plugin_name}': {e}")
            else:
                print(f"Plugin '{plugin_name}' does not have a valid plugin.json file.")

        return plugins_metadata

    def get_plugins_by_category(self):
        """Returns plugins grouped by categories."""
        plugins_metadata = self.get_activated_plugins()
        plugins_by_category = {}

        for plugin_name, metadata in plugins_metadata.items():
            category = metadata.get("category", "Uncategorized")
            if category not in plugins_by_category:
                plugins_by_category[category] = []
            plugins_by_category[category].append({
                "name": plugin_name,
                "active": metadata.get("active", False),
                # Other metadata you might need
                "layout": metadata.get("layout", {})
            })
        
        return plugins_by_category
    
    def get_plugins_metadata(self):
        """Gathers metadata for all plugins from their respective plugin.json files."""
        plugin_folder = "plugins"
        plugins_metadata = {}

        for plugin_name in os.listdir(plugin_folder):
            plugin_path = os.path.join(plugin_folder, plugin_name)
            metadata_file = os.path.join(plugin_path, 'plugin.json')
            if os.path.isdir(plugin_path) and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r') as f:
                        plugins_metadata[plugin_name] = json.load(f)
                except (OSError, json.JSONDecodeError) as e:
                    print(f"Error loading metadata for plugin '{plugin_name}': {e}")

        return plugins_metadata

    def get_frontend_components(self):
        components = []
        for plugin in self.plugins:
            frontend_components = self.plugin_manager.hook.get_frontend_components(plugin=plugin)
            components.extend(frontend_components)
        return components

    def startup_plugins(self):
        """Calls the startup method on all registered plugins."""
        self.plugin_manager.hook.startup()
        
    def get_plugin_manager(self):
        return self
    
    def call_speak_hook(self, message):
        """Trigger the speak hook with a message"""
        for result in self.plugin_manager.hook.speak(message=message):
            # Process each result if necessary
            print(result)
            
    def activate_plugin(self, plugin_name):
        """Activates a plugin by setting its 'active' status to True in its plugin.json."""
        self._set_plugin_active_status(plugin_name, True)
        self._trigger_plugin_hook(plugin_name, 'activate')

    def deactivate_plugin(self, plugin_name):
        """Deactivates a plugin by setting its 'active' status to False in its plugin.json."""
        self._set_plugin_active_status(plugin_name, False)
        self._trigger_plugin_hook(plugin_name, 'deactivate')

    def _set_plugin_active_status(self, plugin_name, status):
        """Helper method to update the 'active' status of a plugin."""
        plugin_folder = "plugins"
        metadata_file = os.path.join(plugin_folder, plugin_name, 'plugin.json')

        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                metadata['active'] = status

                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=4)

                print(f"Plugin '{plugin_name}' has been {'activated' if status else 'deactivated'}.")
            except (OSError, json.JSONDecodeError) as e:
                print(f"Error updating active status for plugin '{plugin_name}': {e}")
        else:
            print(f"Plugin '{plugin_name}' does not have a valid plugin.json file.")
            
    def _trigger_plugin_hook(self, plugin_name, hook_name):
        """Triggers a specific hook for a given plugin."""
        for plugin in self.plugins:
            if plugin.__class__.__name__.lower() == plugin_name.lower():
                hook = getattr(self.plugin_manager.hook, hook_name)
                hook(plugin=plugin)
                print(f"Triggered '{hook_name}' hook for plugin '{plugin_name}'.")
                break
        else:
            print(f"Plugin '{plugin_name}' not found or not loaded.")