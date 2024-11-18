import importlib.util
import os, sys, asyncio
import json
import pluggy
from settings_manager import SettingsManager
from dotenv import load_dotenv
load_dotenv()
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
    def asr_msg(self, msg: str) -> None:
        """Hook for plugins to perform actions when speaker has said something via ASR"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def query_rag(self, query):
        # Gather all results from the async hook implementations
        results = await asyncio.gather(
            *self.plugin_manager.hook.query_rag(query=query)
        )
        return results  # Return the list of results
        
class PluginManager:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.plugin_folder="plugins"
        self.status_manager = StatusManager()
        self.plugins = []
        self.plugin_manager = pluggy.PluginManager(app_name)
        self.plugin_manager.add_hookspecs(MyAppSpec)

        # Load global settings
        self.settings_manager = SettingsManager()

        # self.set_active_plugins SHOULD COME HERE
        # Load plugins dynamically from the plugins/ directory based on activation state

    
    '''
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
    ''' 
    def trigger_hook(self, hook_name, *args, **kwargs):
        print("Hook triggered:", hook_name)
        """Generic method to trigger any hook by name."""
        hook = getattr(self.plugin_manager.hook, hook_name, None)
        if hook:
            try:
                # If args contains a dictionary, merge it into kwargs
                if args and isinstance(args[0], dict):
                    kwargs.update(args[0])  # Move the dictionary to kwargs

                print(f"Executing hook with kwargs: {kwargs}")
                results = hook(**kwargs)  # Pass only keyword arguments to the hook
                for result in results:
                    print(result)
            except Exception as e:
                print(f"Error executing hook '{hook_name}': {e}")
                if IGOOR_DEBUG:
                    print("EXIT BECAUSE OF ERROR EXECUTING HOOK")
                    sys.exit()
        
    def is_active(self, plugin_name):
        is_active = self.all_plugins.get(plugin_name, {}).get("active", False)
        print(f"{plugin_name} is {'active' if is_active else 'NOT active'}")
        return is_active

    '''
    EXPERIMENTAL
    '''
    def load_plugins(self, active_list=None, exclude_list=None):
        print("Loading plugins")
        self.all_plugins = self.get_all_plugins()
        print(len(self.all_plugins), " TOTAL PLUGINS")
        self.activated_plugins = []

        # Default to empty lists if None is provided
        active_list = active_list or []
        exclude_list = exclude_list or []

        for plugin_name in os.listdir(self.plugin_folder):
            if plugin_name != "baseplugin":
                plugin_path = os.path.join(self.plugin_folder, plugin_name)
                is_active = self.is_active(plugin_name)
                
                # Check if the plugin should be activated or excluded based on the lists
                if plugin_name in active_list:
                    print(f"Plugin '{plugin_name}' is in the active_list, overriding is_active to True.")
                    is_active = True
                elif plugin_name in exclude_list:
                    print(f"Plugin '{plugin_name}' is in the exclude_list, overriding is_active to False.")
                    is_active = False

                if os.path.isdir(plugin_path) and is_active:
                    print("Plugin to be activated: ", plugin_name)
                    if plugin_name.lower() not in map(str.lower, self.activated_plugins):
                        print("Plugin ", plugin_name.lower(), " not already activated")
                    try:
                        plugin_module = importlib.import_module(f"plugins.{plugin_name}.{plugin_name}")
                        plugin_class = getattr(plugin_module, f"{plugin_name.capitalize()}")
                        plugin_instance = plugin_class(plugin_name, self)
                        print("Passing plugin instance of class ", plugin_class, " to pm")
                        self.plugins.append(plugin_instance)
                        self.plugin_manager.register(plugin_instance)
                        self.status_manager.register_observer(plugin_instance)
                        self.activated_plugins.append(plugin_name)
                    except Exception as e:
                        print(f"Error loading plugin '{plugin_name}': {e}")
                        if IGOOR_DEBUG:
                            print("EXIT BECAUSE OF ERROR LOADING PLUGIN")
                            os._exit(1)
                else:
                    print(f"Skipping plugin '{plugin_name}'")
            else:
                print("Excluded baseplugin")
        
        print("ACTIVATED PLUGINS LIST:", self.activated_plugins)


    '''
    SAFE VERSION
    def load_plugins(self):
        print("Loading plugins")
        self.all_plugins = self.get_all_plugins()
        print(len(self.all_plugins), " TOTAL PLUGINS")
        self.activated_plugins = []
        for plugin_name in os.listdir(self.plugin_folder):
            if not plugin_name == "baseplugin": 
                plugin_path = os.path.join(self.plugin_folder, plugin_name)
                if os.path.isdir(plugin_path) and self.is_active(plugin_name):
                    print ("plugin to be activated: ", plugin_name)
                    if (plugin_name.lower() not in map(str.lower, self.activated_plugins)):
                        print ("plugin ", plugin_name.lower(), " not already activated")
                    try:
                        plugin_module = importlib.import_module(f"plugins.{plugin_name}.{plugin_name}")
                        plugin_class = getattr(plugin_module, f"{plugin_name.capitalize()}")
                        plugin_instance = plugin_class(plugin_name, self)
                        print("passing plugin instance of class ", plugin_class, " a pm")
                        self.plugins.append(plugin_instance)
                        self.plugin_manager.register(plugin_instance)
                        self.status_manager.register_observer(plugin_instance)
                        self.activated_plugins.append(plugin_name)
                    except Exception as e:
                        print(f"Error loading plugin '{plugin_name}': {e}")
                        if IGOOR_DEBUG:
                            print("EXIT BECAUSE OF ERROR LOADING PLUGIN")
                            os._exit(1)
            else:
                print("Excluded baseplugin")
        print("ACTIVATED PLUGINS LIST:", self.activated_plugins)
    '''

    def get_all_plugins(self):
        """Gathers activation status and other metadata for all plugins."""
        plugins_metadata = {}

        for plugin_name in os.listdir(self.plugin_folder):
            plugin_path = os.path.join(self.plugin_folder, plugin_name)
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
        
        plugins_metadata = self.get_all_plugins()
        plugins_by_category = {}
        excluded_plugins = ["baseplugin", "settings"]
        for plugin_name, metadata in plugins_metadata.items():
            if plugin_name.lower() not in map(str.lower, excluded_plugins):
                category = metadata.get("category", "Uncategorized")
                if category not in plugins_by_category:
                    plugins_by_category[category] = []
                plugins_by_category[category].append({
                    "name": plugin_name,
                    "title": metadata.get("title", False),
                    "active": metadata.get("active", False),
                    # Other metadata you might need
                    "layout": metadata.get("layout", {}),
                    "is_free": metadata.get("is_free", {}),
                    "requires_subscription": metadata.get("requires_subscription", {}),
                    "requires_internet": metadata.get("requires_internet", {}),
                })
        return plugins_by_category
    
    def get_plugins_metadata(self):
        """Gathers metadata for all plugins from their respective plugin.json files."""
        plugins_metadata = {}

        for plugin_name in os.listdir(self.plugin_folder):
            plugin_path = os.path.join(self.plugin_folder, plugin_name)
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
    
    '''
    def call_speak_hook(self, message):
        """Trigger the speak hook with a message"""
        for result in self.plugin_manager.hook.speak(message=message):
            # Process each result if necessary
            print(result)
    '''
    def plugin_has_settings(self, plugin_name, return_settings=False):
        settings = self.settings_manager.get_plugin_settings(plugin_name)
        # Check if settings is a valid non-empty dictionary
        if isinstance(settings, dict) and settings:
            if not return_settings:
                return True
            else:
                return settings
        return False
    
    '''
    If the plugin has a settings.json file, it will be added to the global settings.json file
    if it does not already exist
    '''
    def set_def_plugin_settings(self, plugin_name):
        settings_file_path = os.path.join('plugins', plugin_name, 'settings.json')
        print("Searching for: " + settings_file_path)
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                try:
                    plugin_settings = json.load(f)
                    self.settings_manager.update_plugin_settings(plugin_name, plugin_settings)
                except json.JSONDecodeError:
                    print(f"Invalid JSON in {settings_file_path}.")
        else:
            print(f"Settings file not found for plugin: {plugin_name}")
            
    def activate_plugin(self, plugin_name):
        """Activates a plugin by setting its 'active' status to True in its plugin.json."""
        self._set_plugin_active_status(plugin_name, True)
        if not self.plugin_has_settings(plugin_name):
            self.set_def_plugin_settings(plugin_name)
        else:
            print("Keeping original settings")
        self._trigger_plugin_hook(plugin_name, 'activate')

    def deactivate_plugin(self, plugin_name):
        """Deactivates a plugin by setting its 'active' status to False in its plugin.json."""
        self._set_plugin_active_status(plugin_name, False)
        self._trigger_plugin_hook(plugin_name, 'deactivate')

    def _set_plugin_active_status(self, plugin_name, status):
        """Helper method to update the 'active' status of a plugin."""
        metadata_file = os.path.join(self.plugin_folder, plugin_name, 'plugin.json')

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
            

            
    def call_target_function(self, module_name, target_function_name, args):
        print("calling target function", target_function_name, "in", module_name)
        plugin = self.plugin_manager.get_plugin(module_name)
        if plugin:
            func = getattr(plugin, target_function_name, None)
            if func and callable(func):
                return func(*args)
        raise Exception(f"Function {target_function_name} not found in module {module_name}")
    
    '''
        Experimental
    '''
    def set_active_plugins(self, activate_list=None, exclude_list=None):
        """
        Activates only the plugins in the activate_list and excludes those in the exclude_list.
        If activate_list is None, all plugins are considered for activation except those in exclude_list.
        """
        activate_list = activate_list or []
        exclude_list = exclude_list or []

        # Get all plugins
        all_plugins = self.get_all_plugins()

        for plugin_name in all_plugins:
            if plugin_name in exclude_list:
                self.deactivate_plugin(plugin_name)
            elif not activate_list or plugin_name in activate_list:
                self.activate_plugin(plugin_name)