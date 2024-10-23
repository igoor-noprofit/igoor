from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl 


class Flow(Baseplugin):
    @hookimpl
    def startup(self):
        print("STARTUPSELF")