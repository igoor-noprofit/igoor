from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl 

class Flow(Baseplugin):
    def __init__(self, plugin_name="flow"):
        super().__init__(plugin_name)
        self.status_manager.register_observer(self)  # Register this plugin as an observer

    @hookimpl
    def startup(self):
        print("STARTUPSELF")
        
    @hookimpl
    def activate(self):
        print ("Cool, I'm being activated!")  
        
    @hookimpl
    def deactivate(self):
        print ("Sorry to see you go!")     
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")