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

    
    def process_incoming_message(self, message):
        """
        Process the incoming message from the frontend.
        
        :param message: The message received from the WebSocket.
        """        
        try:
            if isinstance(message, str):
                message = json.loads(message)
                
            # Handle structured messages with actions
            if isinstance(message, dict):
                if message.get('action') == 'save_settings':
                    return self.handle_save_settings(message.get('data', {}))
                
                # Legacy support for direct settings update
                return self.handle_save_settings(message)
                
        except json.JSONDecodeError as e:
            print(f"Error processing message: {e}")
            self.send_message_to_frontend({
                'type': 'error',
                'message': 'Invalid message format'
            })
    
    def handle_save_settings(self, new_settings):
        """
        Handle saving of new settings.
        
        :param new_settings: Dictionary containing the new settings
        """
        try:
            # Debug logging
            print(f"Settings Manager available: {hasattr(self.pm, 'settings_manager')}")
            print(f"Received settings to save: {json.dumps(new_settings, indent=2)}")
            
            # Validate mandatory fields
            mandatory_check, missing_info = self.check_mandatory_fields(new_settings)
            print(f"Mandatory check result: {mandatory_check}, Missing info: {missing_info}")
            
            if mandatory_check:
                try:
                    # Get current settings to preserve any existing values not in new_settings
                    current_settings = self.pm.settings_manager.get_plugin_settings('onboarding') or {}
                    
                    # Update each section separately to preserve structure
                    for section in ['bio', 'prefs', 'ai']:
                        if section in new_settings:
                            if section not in current_settings:
                                current_settings[section] = {}
                            current_settings[section].update(new_settings[section])
                    
                    # Save the updated settings using update_plugin_settings
                    self.pm.settings_manager.update_plugin_settings('onboarding', current_settings)
                    print("Settings saved successfully")
                    
                    # Update local settings
                    self.settings = current_settings
                    self.onboarding_completed = True
                    
                    # Switch view
                    asyncio.create_task(self.send_switch_view_to_app('daily'))
                    
                    # Send success response
                    self.send_message_to_frontend({
                        'type': 'success',
                        'message': 'Settings saved successfully'
                    })
                    
                except Exception as save_error:
                    print(f"Error during save operation: {str(save_error)}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    raise save_error
            else:
                error_msg = f'Missing required field: {missing_info["missing_field"]} in {missing_info["category"]}'
                print(f"Validation failed: {error_msg}")
                self.send_message_to_frontend({
                    'type': 'error',
                    'message': error_msg
                })
                
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.send_message_to_frontend({
                'type': 'error',
                'message': f'Failed to save settings: {str(e)}'
            })
        
    @hookimpl
    async def gui_ready(self):
        print("GUI READY!")
        view = 'daily' if self.onboarding_completed else 'onboarding'
        await self.send_switch_view_to_app(view)
        self.send_message_to_frontend(self.settings)
        
        