from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl 


class Flow:
    @hookimpl
    def startup(self):
        print("STARTUPSELF")