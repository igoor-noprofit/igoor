from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor


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
    def asr_msg(self, msg: str) -> None:
        print(f"QUERYING RAG WITH: {msg}")
        with ThreadPoolExecutor() as executor:
            executor.submit(self.pm.trigger_hook, hook_name="query_rag", query_text=msg)
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")