from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import asyncio
from dotenv import load_dotenv
load_dotenv()
from context_manager import context_manager


class Onboarding(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.onboarding_completed = False
        super().__init__(plugin_name,pm)

    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        ''' check all mandatory settings are not empty
        if it's the case, send message to frontend to hide '''
        mandatory_fields = {
            "bio": ["name", "health_state"],
            "ai": ["api_key","model","provider"]
        }

        for category, fields in mandatory_fields.items():
            category_settings = self.settings.get(category, {})
            
            # Debug: Print the category settings being checked
            print(f"Checking category '{category}':", category_settings)
            
            for field in fields:
                if not category_settings.get(field):
                    # Debug: Print which field is missing
                    print(f"Missing field '{field}' in category '{category}'")
                    return False
                
        print("ONBOARDING COMPLETED!")
        self.onboarding_completed = True
    
    
    
    @hookimpl
    async def gui_ready(self):
        print("GUI READY!")
        if self.onboarding_completed:
            await self.send_switch_view_to_app('flow')