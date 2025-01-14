import asyncio
import webview
# from prompts import AssistantPrompts
from context_manager import ContextManager
context_manager = ContextManager()
from plugin_manager import PluginManager
plugin_manager = PluginManager()
from settings_manager import SettingsManager
import os,time

class Api:
    def __init__(self):
        print("INIT API")
        self.was_fullscreen = os.getenv('IGOOR_FULLSCREEN', 'False').lower() == 'true'
        self.initial_width = 1920  # Or your preferred default width
        self.initial_height = 1080  # Or your preferred default height
        
    def get_plugins_by_category(self):
        print("Fetching plugins by category")
        return plugin_manager.get_plugins_by_category()
    
    def get_plugin_settings(self,plugin_name):
        print("Fetching plugin settings")
        return plugin_manager.plugin_has_settings(plugin_name,True)
    
    def toggle_plugin(self, pn, active):
        if not active:
            return plugin_manager.deactivate_plugin(plugin_name=pn)
        else:
            return plugin_manager.activate_plugin(plugin_name=pn)

    def minimize(self):
        print("MIN window")
        window = webview.windows[0]
        # Exit fullscreen if needed
        if window.fullscreen:
            window.toggle_fullscreen()
            # Add a small delay to ensure fullscreen exit completes
            time.sleep(0.1)
        window_x = 0
        window_y = 0  # Y position
        print(f"Moving to {window_x},{window_y}")
        window.resize(96, 96)
        window.move(window_x, window_y)
        window.on_top = True  # 

    def maximize(self):
        try:
            print("MAX window")
            window = webview.windows[0]
            window.on_top = False  # Disable on_top when maximizing
            # First restore to normal size
            window.resize(self.initial_width, self.initial_height)
            time.sleep(0.1)

            # If it was fullscreen before or should be fullscreen by default
            if self.was_fullscreen:
                window.toggle_fullscreen()
        except Exception as e:
            print(f"Error during maximize: {e}")
        
    
    def change_view(self,lastview,currentview):
        asyncio.run(self.trigger_hook("change_view",lastview=lastview,currentview=currentview))
    
    def get_context_all(self):
        print(context_manager.get_context())
        
    async def trigger_hook(self, hook_name, *args, **kwargs):
        try:
            print(f"JS : triggering hook {hook_name} with args: {args} and kwargs: {kwargs}")
            result = await plugin_manager.trigger_hook(hook_name, *args, **kwargs)
            print(result)     
            # Ensure the result is JSON serializable
            if isinstance(result, (list, dict, str, int, float, bool, type(None))):
                return result
            else:
                print("Result is not JSON serializable")
                return None
        except Exception as e:
            print(f"Error triggering hook '{hook_name}': {e}")
            return None