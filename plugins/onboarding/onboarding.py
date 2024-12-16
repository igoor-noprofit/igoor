from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import json
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
        self.mandatory_fields = {
            "bio": ["name", "health_state"],
            "ai": ["api_key","model_name","provider"],
            "prefs": ["lang"]
        }
        mandatory_check, missing_info = self.check_mandatory_fields(self.settings)
        if mandatory_check:
            print("ONBOARDING COMPLETED!")
            self.onboarding_completed = True
        
    def check_mandatory_fields(self, settings_json):
        """
        Check if all mandatory fields are present in the settings JSON.

        :param settings_json: The settings JSON object to check.
        :return: True if all mandatory fields are present, False otherwise.
        """
        for category, fields in self.mandatory_fields.items():
            category_settings = settings_json.get(category, {})
            
            # Debug: Print the category settings being checked
            print(f"Checking category '{category}':", category_settings)
            
            for field in fields:
                if not category_settings.get(field):
                    # Debug: Print which field is missing
                    print(f"Missing field '{field}' in category '{category}'")
                    missing_info = {"missing_field": field, "category": category}
                    print("Returning missing info as JSON:", json.dumps(missing_info))
                    return False, missing_info
        return True, None

    
    def process_incoming_message(self, new_settings):
        """
        Process the incoming message.
        
        :param message: The message received from the WebSocket.
        """        
        try:
            # Attempt to parse the message as JSON
            mandatory_check, missing_info = self.check_mandatory_fields(new_settings)
            if mandatory_check:
                self.mass_update_settings(new_settings)
                asyncio.create_task(self.send_switch_view_to_app('daily'))
            else: 
                self.send_message_to_frontend(missing_info)
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
    
    
    @hookimpl
    async def gui_ready(self):
        print("GUI READY!")
        view = 'flow' if self.onboarding_completed else 'onboarding'
        await self.send_switch_view_to_app(view)
        self.send_message_to_frontend(self.settings)
        
        