import asyncio
import os

import webview
# from prompts import AssistantPrompts
from context_manager import ContextManager
context_manager = ContextManager()
from plugin_manager import PluginManager
plugin_manager = PluginManager()

class Api:
    def __init__(self):
        self.language = os.getenv("IGOOR_LANG")
        # self.prompts = AssistantPrompts("locales/", self.language)
        self.igoor_engine = os.getenv("IGOOR_AI_ENGINE")
        
    def get_plugins_by_category(self):
        print("Fetching plugins by category")
        return plugin_manager.get_plugins_by_category()
    
    def toggle_plugin(self, pn, active):
        if not active:
            return plugin_manager.deactivate_plugin(plugin_name=pn)
        else:
            return plugin_manager.activate_plugin(plugin_name=pn)

    async def askAI(self, assistant_type, query):
        print("received query = " + query)
        system_prompt = self.prompts.get_system_prompt(self.language, assistant_type)
        if (self.igoor_engine == 'openai'):
            response = await query_rag_openai(system_prompt, query);
        else:
            response = await query_rag(system_prompt, query);
            print("*** RESPONSE CONTENT ***")
            print (response.content)
            print("*** END RESPONSE CONTENT ***")
        return response

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
        
    '''
        Replace with websocket?
        Calls ANY plugin backend function specifically ?
    '''
    def call_plugin_backend(self, module_name, target_function_name, args):
        print("call backend of plugin", module_name)
        if module_name:
            return plugin_manager.call_target_function(module_name, target_function_name, args)
        else:
            raise ValueError("Module name is required")
        
    def trigger_hook(self, hook_name, *args, **kwargs):
        print(f"JS : triggering hook {hook_name} with args: {args} and kwargs: {kwargs}")
        plugin_manager.trigger_hook(hook_name, *args, **kwargs)     