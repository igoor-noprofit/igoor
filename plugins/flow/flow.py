from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
import asyncio


class Flow(Baseplugin):
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        # self.status_manager.register_observer(self)  # Register this plugin as an observer

    @hookimpl
    def startup(self):
        print("STARTUPSELF")
        
    @hookimpl
    def activate(self):
        print ("Activating flow")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating FLOW")     
    
    @hookimpl
    async def asr_msg(self, msg: str) -> None:
        print(f"QUERYING RAG WITH: {msg}")
        result = await(self.query_rag_async(msg))
        print(f"CONTEXT IS : {result}")
        
        
    async def query_rag_async(self, msg: str):
        # Await the async hook call
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        print (f"Result of query_rag_async: {result}")
        return result
                
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")