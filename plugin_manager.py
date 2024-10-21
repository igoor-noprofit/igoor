import importlib.util
import os
import json
import pluggy

hookspec = pluggy.HookspecMarker("myapp")
hookimpl = pluggy.HookimplMarker("myapp")

class MyAppSpec:
    @pluggy.HookspecMarker("myapp")
    def get_frontend_components(self):
        """Hook for plugins to provide frontend components"""
        pass

class PluginManager:
    def __init__(self):
        self.plugins = []
        self.plugin_manager = pluggy.PluginManager("myapp")
        self.plugin_manager.add_hookspecs(MyAppSpec)

        # Load plugins dynamically from the plugins/ directory based on activation state
        self.load_plugins()

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
                except Exception as e:
                    print(f"Error loading plugin '{plugin_name}': {e}")

    def get_activated_plugins(self):
        config_file = 'plugins_config.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            print(f"Configuration file '{config_file}' not found. All plugins will be considered inactive.")
            return {}

    def get_frontend_components(self):
        components = []
        for plugin in self.plugins:
            frontend_components = self.plugin_manager.hook.get_frontend_components(plugin=plugin)
            components.extend(frontend_components)
        return components
