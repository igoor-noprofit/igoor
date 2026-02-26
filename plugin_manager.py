from version import __appname__, __version__, __codename__
import importlib.util
import os, sys, asyncio
import threading
import time
import json
import traceback
import pluggy
from settings_manager import SettingsManager
from dotenv import load_dotenv
load_dotenv()
from typing import Any
from status_manager import StatusManager
from utils import resource_path, setup_logger
from websocket_server import websocket_server

IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
app_name = __appname__
hookspec = pluggy.HookspecMarker(app_name)
hookimpl = pluggy.HookimplMarker(app_name)
logger = setup_logger('pm', os.path.join(os.getenv('APPDATA'), app_name))

class MyAppSpec:
    '''
        ************ PLUGINS CYCLE **************
    '''
    @pluggy.HookspecMarker(app_name)
    def activate(self):
        """Hook for plugins to perform actions upon activation."""
        pass

    @pluggy.HookspecMarker(app_name)
    def deactivate(self):
        """Hook for plugins to perform actions upon deactivation."""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def get_frontend_components(self):
        """Hook for plugins to provide frontend components"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def startup(self):
        """Hook for plugins to perform startup activities"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def run_tests(self):
        """Hook for plugins to perform startup activities"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def custom_save_settings(self,plugin_name:str,settings):
        """Hook for plugins to perform custom save settings"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def settings_updated(self, plugin_name: str, new_settings: dict):
        """Hook called when a plugin's settings are updated"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def global_settings_updated(self):
        """Hook called when entire settings are updated"""
        pass
    
    '''
        GUI AND APP
    '''
    @pluggy.HookspecMarker(app_name)
    async def gui_ready(self):
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def change_view(self,lastview,currentview):
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def onboarding_toggled(self,is_onboarding):
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def user_idle_on_pc(self):
        """Hook for when the user is completely idle on the PC """
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def force_onboarding(self):
        """Hook to force the user to the onboarding plugin """
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def igoor_is_maximized(self):
        """Hook for when the user maximizes IGOOR's window """
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def igoor_is_minimized(self):
        """hook for when the user minimizes IGOOR's window """
        pass
    
    '''
        ************ TTS **************
    '''
    
    @pluggy.HookspecMarker(app_name)
    def speak(self,message: str):
        pass
    
    @pluggy.HookspecMarker(app_name)
    def speak_fallback(self,message: str):
        """ Fallback function if main TTS fails """
        pass
    
    @pluggy.HookspecMarker(app_name)
    def speak_as_igoor(self,message: str):
        pass
    
    '''
        ************ ASR **************
    '''
    
    @pluggy.HookspecMarker(app_name)
    def wakeword_detected(self):
        """Hook for optional separate wake word mechanism """
        pass
        
    @pluggy.HookspecMarker(app_name)
    def process_wake_word(self, text):
        """Hook for processing wake word detected text"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def pause_asr(self):
        pass
    
    @pluggy.HookspecMarker(app_name)
    def restart_asr(self):
        pass

    @pluggy.HookspecMarker(app_name)
    async def asr_msg(self, msg: str) -> None:
        """Hook for plugins to perform actions when speaker has said something via ASR"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def start_recording(self) -> None:
        """Hook for plugins to perform actions when speaker starts recording"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def stop_recording(self) -> None:
        """Hook for plugins to perform actions when speaker stops recording"""      
        pass
    
    
    '''
        ************ CONVERSATION **************
    '''
    
    @pluggy.HookspecMarker(app_name)
    def set_conversation_topic(self,topic:str):
        """Hook for triggering actions related to new conversation"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def new_conversation(self):
        """Hook for triggering actions related to new conversation"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def add_msg_to_conversation(self, msg, author, msg_input):
        """Hook for processing wake word detected text"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def abandon_conversation(self, cause):
        """Hook for abandoning current conversation"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def after_conversation_end(self, last_conversation):
        """Hook to analyze or do other stuff with last conversation"""
        pass

    
    @pluggy.HookspecMarker(app_name)
    def reset_conversation_timeout(self):
        """Hook to reset conversation timeout when user does something"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def get_conversation_msgs_containing(self, query_text: str):
        """Hook to search previous conversation messages containing query for autocomplete etc."""
        pass

    @pluggy.HookspecMarker(app_name)
    def get_last_conversations(self):
        """Hook to retrieve cached last conversations for LLM context"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def transcribing_started(self):
        """Hook to communicate with plugins that transcription has started"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def transcribing_ended(self):
        """Hook to communicate with plugins that transcription has ended"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def process_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000):
        """Hook for processing audio chunks in real-time (e.g., speaker identification)"""
        pass
    
    '''
        ************ AI FLOW AND RAG **************
    '''
    @pluggy.HookspecMarker(app_name)
    def rag_loaded(self):
        """Hook for plugins to perform actions when RAG is loaded"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def send_prompt(self, prompt: str) -> None:
        """Hook for plugins to perform actions when sending prompt"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def query_rag(self, query_text: str, store_types: list, return_chunk_ids:bool):
        # Gather all results from the async hook implementations
        pass
        
    @pluggy.HookspecMarker(app_name)
    async def store_memory(self, fact: str,type: int,conversation_id:int,theme:str,tags:list, reason:str, created_at: None):        
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def filter_by_timeframe(self, preflow_dict: dict, docstore_ids_by_type: dict):        
        pass
    
    @pluggy.HookspecMarker(app_name)
    async def clean_short_term_memory(self, clean_after_days:int):        
        pass
    
    '''
        ************ AUTOCOMPLETE **************
    '''
    @pluggy.HookspecMarker(app_name)
    def store_autocomplete_prediction(self, input_text: str, completion: str):
        """Hook for storing successful autocomplete predictions"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def show_virtual_keyboard(self):
        """Hook for displaying virtual keyboard"""
        pass
    
    @pluggy.HookspecMarker(app_name)
    def hide_virtual_keyboard(self):
        """Hook for hiding virtual keyboard"""
        pass    
    

    
class PluginManager:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.logger = logger  
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.plugin_folder=resource_path('plugins')
        self.status_manager = StatusManager()
        self.fastapi_app = None
        self.plugins = []
        self.plugin_manager = pluggy.PluginManager(app_name)
        self.plugin_manager.add_hookspecs(MyAppSpec)
        self._boot_progress_thread = None
        self._boot_progress_stop = threading.Event()
        self._boot_progress_started_at = None
        self._boot_progress_total = 0

        # Load global settings
        self.settings_manager = SettingsManager()

        # self.set_active_plugins SHOULD COME HERE
        # Load plugins dynamically from the plugins/ directory based on activation state

    async def trigger_hook(self, hook_name, **kwargs):
        self.logger.info(f"Hook triggered: {hook_name}")
        """Generic method to trigger any hook by name."""
        hook = getattr(self.plugin_manager.hook, hook_name, None)
        if hook:
            try:
                # Log the kwargs that will be passed to the hook
                self.logger.info(f"Executing hook {hook_name} with kwargs: {str(kwargs)[:50]} ...")                
                # Call the hook with unpacked kwargs
                results = hook(**kwargs)

                # Ensure results is an awaitable
                if asyncio.iscoroutine(results) or isinstance(results, asyncio.Future):
                    results = await results  # Await if it's a single coroutine or Future
                elif isinstance(results, list):
                    # Process mixed list of coroutines and regular values
                    processed_results = []
                    for r in results:
                        if asyncio.iscoroutine(r) or isinstance(r, asyncio.Future):
                            processed_results.append(await r)
                        else:
                            processed_results.append(r)
                    results = processed_results
                else:
                    raise TypeError("The hook result is not awaitable")

                # Return all results
                return results
            except Exception as e:
                self.logger.error(f"Error executing hook '{hook_name}': {e}")
                if IGOOR_DEBUG:
                    self.logger.critical("EXIT BECAUSE OF ERROR EXECUTING HOOK")
                    sys.exit()
        else:
            self.logger.warning(f"Hook '{hook_name}' not found.")
            return None
    
    def is_active(self, plugin_name):
        """Check if a plugin is active based on settings.json"""
        settings = self.settings_manager.get_settings()
        plugins_activation = settings.get("plugins_activation", {})
        
        # If plugin isn't in settings.json yet, get default from plugin.json (for migration)
        if plugin_name not in plugins_activation:
            default_active = self.all_plugins.get(plugin_name, {}).get("active", False)
            self._set_plugin_active_status(plugin_name, default_active)
            return default_active
            
        return plugins_activation.get(plugin_name, False)


    '''
    EXPERIMENTAL
    '''
    def load_plugins(self, active_list=None, exclude_list=None):
        self.logger.info("Loading plugins")
        self.all_plugins = self.get_all_plugins()
        self.logger.info(f"{len(self.all_plugins)} TOTAL PLUGINS")
        self.activated_plugins = []

        # Default to empty lists if None is provided
        active_list = active_list or []
        exclude_list = exclude_list or []

        for plugin_name in os.listdir(self.plugin_folder):
            if plugin_name != "baseplugin":
                plugin_path = os.path.join(self.plugin_folder, plugin_name)
                is_active = self.is_active(plugin_name)
                self.logger.info (f": {plugin_path}")
                try:
                    # Update splash/loading status while starting up
                    self.status_manager.set_status(f"Loading plugin {plugin_name}")
                except Exception:
                    pass
                # Check if the plugin should be activated or excluded based on the lists
                if plugin_name in active_list:
                    self.logger.info(f"Plugin '{plugin_name}' is in the active_list, overriding is_active to True.")
                    is_active = True
                elif plugin_name in exclude_list:
                    self.logger.info(f"Plugin '{plugin_name}' is in the exclude_list, overriding is_active to False.")
                    is_active = False

                if os.path.isdir(plugin_path) and is_active:
                    self.logger.info(f"Plugin to be activated: {plugin_name}")
                    # if plugin_name.lower() not in map(str.lower, self.activated_plugins):
                        # self.logger.info(f"Plugin {plugin_name.lower()} not already activated")
                    try:
                        plugin_module = importlib.import_module(f"plugins.{plugin_name}.{plugin_name}")
                        plugin_class = getattr(plugin_module, f"{plugin_name.capitalize()}")
                        plugin_instance = plugin_class(plugin_name, self)
                        self.plugins.append(plugin_instance)
                        self.plugin_manager.register(plugin_instance)
                        self.status_manager.register_observer(plugin_instance)
                        self.activated_plugins.append(plugin_name)
                        self.copy_default_plugin_settings_if_needed(plugin_name)
                    except Exception as e:
                        self.logger.error(f"Error loading plugin '{plugin_name}': {e}")
                        self.logger.error(f"Traceback: {traceback.format_exc()}")
                        if IGOOR_DEBUG:
                            self.logger.critical("EXIT BECAUSE OF ERROR LOADING PLUGIN")
                            os._exit(1)
                else:
                    self.logger.info(f"Skipping plugin '{plugin_name}'")
            else:
                print("Excluded baseplugin")
        
        self.logger.info(f"ACTIVATED PLUGINS LIST: {self.activated_plugins}")
        try:
            self.status_manager.set_status("Starting plugins…")
        except Exception:
            pass
        self.startup_plugins()
        self._start_boot_progress_monitor()


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
                    self.logger.error(f"Error loading metadata for plugin '{plugin_name}': {e}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.warning(f"Plugin '{plugin_name}' does not have a valid plugin.json file.")

        return plugins_metadata

    def get_plugins_by_category(self):
        """Get all plugins organized by category"""
        plugins_by_category = {}
        
        # Get current activation states
        settings = self.settings_manager.get_settings()
        plugins_activation = settings.get("plugins_activation", {})
        self.logger.info(f"Current activation states: {plugins_activation}")
        
        # Get all plugins
        all_plugins = self.get_all_plugins()
        
        # Organize plugins by category
        for plugin_name, metadata in all_plugins.items():
            category = metadata.get("category", "other").lower()
            if category not in plugins_by_category:
                plugins_by_category[category] = []
                
            plugin_info = {
                "name": plugin_name,
                "title": metadata.get("title", plugin_name),
                "description": metadata.get("description", ""),
                "requires_internet": metadata.get("requires_internet", False),
                "requires_subscription": metadata.get("requires_subscription", False),
                "is_free": metadata.get("is_free", True),
                "category": category,
                "active": plugins_activation.get(plugin_name, False),  # Get activation state from settings.json
                "has_settings": metadata.get("has_settings", False)
            }
            
            plugins_by_category[category].append(plugin_info)
        
        return plugins_by_category
    
    def get_plugins_metadata(self):
        """Gathers metadata for all plugins from their respective plugin.json files."""
        plugins_metadata = {}
        print(f"Plugin folder: {self.plugin_folder}")
        for plugin_name in os.listdir(self.plugin_folder):
            plugin_path = os.path.join(self.plugin_folder, plugin_name)
            metadata_file = os.path.join(plugin_path, 'plugin.json')
            if os.path.isdir(plugin_path) and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r') as f:
                        plugins_metadata[plugin_name] = json.load(f)
                except (OSError, json.JSONDecodeError) as e:
                    self.logger.error(f"Error loading metadata for plugin '{plugin_name}': {e}")

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

    def _start_boot_progress_monitor(self):
        if self._boot_progress_thread and self._boot_progress_thread.is_alive():
            return
        self._boot_progress_stop.clear()
        self._boot_progress_started_at = time.time()
        self._boot_progress_total = len(self.activated_plugins)

        def run():
            while not self._boot_progress_stop.is_set():
                total = self._boot_progress_total
                ready_plugins = [plugin for plugin in self.plugins if getattr(plugin, "ready", False)]
                not_ready_plugins = [
                    getattr(plugin, "plugin_name", plugin.__class__.__name__)
                    for plugin in self.plugins
                    if not getattr(plugin, "ready", False)
                ]
                ready = len(ready_plugins)
                if total > 0:
                    payload = {
                        "type": "boot_progress",
                        "ready": ready,
                        "total": total,
                        "not_ready": not_ready_plugins,
                    }
                    try:
                        websocket_server.send_message("app", json.dumps(payload))
                    except Exception:
                        pass
                    try:
                        self.status_manager.set_status(f"Ready {ready}/{total}")
                    except Exception:
                        pass
                if total > 0 and ready >= total:
                    self._boot_progress_stop.set()
                    break
                if time.time() - self._boot_progress_started_at >= 600:
                    self._boot_progress_stop.set()
                    break
                time.sleep(1)

        self._boot_progress_thread = threading.Thread(target=run, daemon=True)
        self._boot_progress_thread.start()
        
    def get_plugin_manager(self):
        return self

    def attach_fastapi_app(self, app):
        self.fastapi_app = app
    
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
        settings_file_path = resource_path(os.path.join('plugins', plugin_name, 'settings.json'))
        self.logger.info(f"Searching for: {settings_file_path}")
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r', encoding='utf-8') as f:
                try:
                    plugin_settings = json.load(f)
                    self.settings_manager.update_plugin_settings(plugin_name, plugin_settings)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON in {settings_file_path}: {e}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            self.logger.warning(f"Settings file not found for plugin: {plugin_name}")
    
    def copy_default_plugin_settings_if_needed(self,plugin_name):
        if not self.plugin_has_settings(plugin_name):
            self.set_def_plugin_settings(plugin_name)
        else:
            print("Keeping original settings")
            
    def activate_plugin(self, plugin_name):
        """Activates a plugin by setting its 'active' status to True in its plugin.json."""
        self.logger.info(f"ACTIVATING {plugin_name}")
        self._set_plugin_active_status(plugin_name, True)
        self.copy_default_plugin_settings_if_needed(plugin_name)
        # self._trigger_plugin_hook(plugin_name, 'activate')

    def deactivate_plugin(self, plugin_name):
        """Deactivates a plugin by setting its 'active' status to False in its plugin.json."""
        self._set_plugin_active_status(plugin_name, False)
        # self._trigger_plugin_hook(plugin_name, 'deactivate')

    def _set_plugin_active_status(self, plugin_name, status):
        """Update plugin activation status in settings.json"""
        settings = self.settings_manager.get_settings()
        if "plugins_activation" not in settings:
            settings["plugins_activation"] = {}
        
        settings["plugins_activation"][plugin_name] = status
        self.settings_manager.save_settings(settings)
        self.logger.info(f"Plugin '{plugin_name}' has been {'activated' if status else 'deactivated'}.")

    def migrate_activation_states(self):
        """Migrate activation states from plugin.json files to settings.json"""
        settings = self.settings_manager.get_settings()
        if "plugins_activation" not in settings:
            settings["plugins_activation"] = {}
            
        # Define core plugins that should be active by default
        core_plugins = {
            "conversation": True,
            "ttsdefault": True,
            "settings": True,
            "onboarding": True,
            "clock": True
        }
        
        # Get all plugins and their metadata
        all_plugins = self.get_all_plugins()
        
        for plugin_name, metadata in all_plugins.items():
            if plugin_name not in settings["plugins_activation"]:
                # If it's a core plugin, use the default state
                if plugin_name in core_plugins:
                    default_state = core_plugins[plugin_name]
                else:
                    # For non-core plugins, check category or set to False
                    is_core = metadata.get("category", "").lower() == "core"
                    default_state = is_core
                
                settings["plugins_activation"][plugin_name] = default_state
        
        self.settings_manager.save_settings(settings)

            
    def call_target_function(self, module_name, target_function_name, args):
        self.logger.info("calling target function", target_function_name, "in", module_name)
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
                
    def are_all_plugins_loaded(self):
        """
        Checks if all active plugins have been loaded.

        Returns:
            tuple:
                bool: True if all active plugins are loaded, False otherwise.
                list: List of plugin names that are not loaded.
                
        USAGE:
            all_loaded, unloaded_plugins = plugin_manager.are_all_plugins_loaded()
        """
        not_loaded = [plugin.name for plugin in self.plugins if not getattr(plugin, 'is_loaded', False)]
        if not_loaded:
            return False, not_loaded
        return True, []
