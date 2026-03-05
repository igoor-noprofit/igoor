from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
from pyowm.owm import OWM
from pyowm.utils.config import get_default_config
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()
from context_manager import context_manager
from settings_manager import SettingsManager
from fastapi import APIRouter, HTTPException

class Onboarding(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        self.sm = SettingsManager()
        self.onboarding_completed = False
        self.router = None
        super().__init__(plugin_name,pm)
    
    @hookimpl
    async def force_onboarding(self):
        print("ONBOARDING PLUGIN is forcing onboard")
        self.onboarding_completed = False
        self.send_message_to_frontend({"action": "show_modal"})

    def _ensure_router(self):
        """Initialize FastAPI router for plugin endpoints"""
        if self.router is not None:
            return
        self.router = APIRouter(prefix="/api/plugins/onboarding", tags=["onboarding"])

        @self.router.get("/validate_api_key")
        async def validate_api_key(provider: str = "groq", api_key: str = "", model_name: str = ""):
            """Validate API key and model for a provider"""
            if not api_key or not api_key.strip():
                raise HTTPException(status_code=400, detail="API key is required")
            if not model_name or not model_name.strip():
                raise HTTPException(status_code=400, detail="Model name is required")

            try:
                if provider == "groq":
                    from groq import Groq
                    client = Groq(api_key=api_key.strip())
                    messages = [{"role": "user", "content": "Hi"}]
                    response = client.chat.completions.create(
                        model=model_name.strip(),
                        messages=messages,
                        max_tokens=5
                    )
                    return {"valid": True}
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
            except Exception as e:
                error_msg = str(e).lower()
                # Handle Groq-specific errors
                if 'unauthorized' in error_msg or 'invalid api key' in error_msg:
                    raise HTTPException(status_code=400, detail="Invalid API Key")
                elif 'unsupported model' in error_msg or '2025' in error_msg:
                    raise HTTPException(status_code=400, detail="Unsupported model")
                elif '401' in error_msg or 'authentication' in error_msg:
                    raise HTTPException(status_code=400, detail="Invalid API Key")
                elif 'timeout' in error_msg or 'connection' in error_msg:
                    raise HTTPException(status_code=400, detail="Connection error: could not validate API key")
                else:
                    raise HTTPException(status_code=400, detail=f"API Key validation failed: {str(e)}")

    @hookimpl
    def startup(self):
        self._ensure_router()
        # Register router with the main FastAPI app if available
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)

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
        self.mark_ready()
        
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
                
        except json.JSONDecodeError as e:
            print(f"Error processing message: {e}")
            self.send_message_to_frontend({
                'type': 'error',
                'message': 'Invalid message format'
            })
    
    def handle_save_settings(self, new_settings):
        self.logger.info("NEW SETTINGS: %s", json.dumps(new_settings, indent=2))
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
                    
                    if (self.mass_update_my_settings(current_settings)):
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
                    else:
                        self.send_error_to_frontend("settings_error","Failed to update settings")
                        
                except Exception as save_error:
                    print(f"Error during save operation: {str(save_error)}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    raise save_error
            else:
                error_msg = f'{missing_info["missing_field"]} in {missing_info["category"]}'
                print(f"Validation failed: {error_msg}")
                self.send_message_to_frontend({
                    'type': 'error',
                    'error_type': 'A mandatory field is missing',
                    'missing_field': missing_info["missing_field"],
                    'category': missing_info["category"]
                })
                # self.send_switch_view_to_app('onboarding')
                
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
    async def global_settings_updated(self):
        """Called when global settings are updated - reload onboarding settings from disk."""
        print("Onboarding: global_settings_updated - reloading settings from disk")
        self.settings = self.get_my_settings()
        # Send updated settings to frontend
        await self.wait_for_socket_and_send(self.settings)

    @hookimpl
    async def gui_ready(self):
        print("GUI READY!")
        view = 'daily' if self.onboarding_completed else 'onboarding'
        await self.send_switch_view_to_app(view)
        await self.wait_for_socket_and_send(self.settings)
    
        
    def get_plugins_by_category(self):
        self.logger.info("Fetching plugins by category in Settings")
        plugins_by_category = plugin_manager.get_plugins_by_category()
        
        # Get current activation states from settings.json
        settings = plugin_manager.settings_manager.get_settings()
        plugins_activation = settings.get("plugins_activation", {})
        self.logger.info(f"Current plugin activation states: {plugins_activation}")
        
        # Update the active status for each plugin
        for category in plugins_by_category:
            for plugin in plugins_by_category[category]:
                plugin_name = plugin["name"]
                # Get activation state from settings.json
                is_active = plugins_activation.get(plugin_name, False)
                self.logger.info(f"Plugin {plugin_name} activation state: {is_active}")
                plugin["active"] = is_active
                
                # Mark core plugins as locked
                plugin["is_core"] = (
                    plugin.get("category", "").lower() == "core" or 
                    plugin_name in ["conversation", "ttsdefault", "settings", "onboarding"]
                )
                
                # Ensure other metadata is included
                if "description" not in plugin:
                    plugin["description"] = plugin_manager.all_plugins.get(plugin_name, {}).get("description", "")
        
        self.logger.info(f"Final plugins by category: {plugins_by_category}")
        return plugins_by_category
        
    def toggle_plugin(self, plugin_name, is_active):
        """Toggle plugin activation state"""
        self.logger.info(f"Toggling plugin {plugin_name} to {is_active}")
        
        # Check if plugin is core
        plugin_metadata = plugin_manager.all_plugins.get(plugin_name, {})
        is_core = (
            plugin_metadata.get("category", "").lower() == "core" or 
            plugin_name in ["conversation", "ttsdefault", "settings", "onboarding"]
        )
        
        if is_core:
            self.logger.warning(f"Attempted to toggle core plugin {plugin_name}")
            return False
        
        # Update settings.json
        settings = plugin_manager.settings_manager.get_settings()
        if "plugins_activation" not in settings:
            settings["plugins_activation"] = {}
        
        settings["plugins_activation"][plugin_name] = is_active
        plugin_manager.settings_manager.save_settings(settings)
        
        # Actually activate/deactivate the plugin
        if is_active:
            plugin_manager.activate_plugin(plugin_name)
        else:
            plugin_manager.deactivate_plugin(plugin_name)
            
        self.logger.info(f"Plugin {plugin_name} toggle complete")
        return True
        