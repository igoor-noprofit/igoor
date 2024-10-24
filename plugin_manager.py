import importlib.util
import os
import json
import pluggy
from settings_manager import SettingsManager
from dotenv import load_dotenv
load_dotenv()
import os
from typing import Any
from status_manager import StatusManager

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

    def load_plugins(self):
        print ("Loading plugins")
        plugin_folder = "plugins"
        activated_plugins = self.get_activated_plugins()
        print("Activated plugins : ", activated_plugins)

        for plugin_name in os.listdir(plugin_folder):
            plugin_path = os.path.join(plugin_folder, plugin_name)
            if os.path.isdir(plugin_path) and activated_plugins.get(plugin_name, False):
                try:
                    plugin_module = importlib.import_module(f"plugins.{plugin_name}.{plugin_name}")
                    plugin_instance = getattr(plugin_module, f"{plugin_name.capitalize()}")()  # Use existing class name
                    self.plugins.append(plugin_instance)
                    self.plugin_manager.register(plugin_instance)
                    self.status_manager.register_observer(plugin_instance)
                except Exception as e:
                    print(f"Error loading plugin '{plugin_name}': {e}")

    def get_activated_plugins(self):
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