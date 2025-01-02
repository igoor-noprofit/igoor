from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from context_manager import context_manager
from settings_manager import SettingsManager
import asyncio,json,time


class Autocompletelauncher(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        '''
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        '''
        self.is_loaded = True