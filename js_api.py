import asyncio
import os

import webview
# from prompts import AssistantPrompts
from context_manager import ContextManager
context_manager = ContextManager()
from plugin_manager import PluginManager
plugin_manager = PluginManager()
from settings_manager import SettingsManager

class Api:
    def __init__(self):
        print("INIT API")
        
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

    def minimize_window(self):
        print("Minimizing window")
        # Get the screen size

        print("Screen size: {}x{}".format(screen_width, screen_height))

        window_x = 0
        window_y = 0 # Y position
        print(f"Moving to {window_x},{window_y}")
        webview.windows[0].resize(96,96)
        webview.windows[0].move(window_x, window_y)

    def maximize_window(self):
        print("MAX window")
        webview.windows[0].resize(screen_width,screen_height)
        
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