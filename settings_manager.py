import json
import os
from pydantic import BaseModel, ValidationError, Field
from typing import Dict

class PluginSettings(BaseModel):
    # Define common schema for plugins; can be expanded as needed
    voice_id: str = None
    api_key: str = None
    model_id: str = None

class AppSettings(BaseModel):
    theme: str = Field(default='light', description="UI Theme")
    notifications_enabled: bool = Field(default=True, description="Enable notifications")
    plugins: Dict[str, PluginSettings] = Field(default_factory=dict, description="Plugin-specific settings")

    @classmethod
    def load_from_file(cls, file_path):
        """
        Load settings from a JSON file. If the file does not exist, return default settings.
        """
        if not os.path.exists(file_path):
            return cls()
        
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                return cls(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Error loading settings file: {e}")
            return cls()  # Return default settings if there's an error

    def save_to_file(self, file_path):
        """
        Save the settings to a JSON file.
        """
        with open(file_path, 'w') as file:
            json.dump(self.dict(), file, indent=4)

    def update_setting(self, key, value):
        """
        Update a setting and save it to the file.
        """
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            print(f"Warning: Setting '{key}' is invalid.")
            
    def as_json(self):
        """
        Return the settings as a JSON-compatible dictionary.
        """
        return self.dict()

def get_settings_file_path(app_name):
    """
    Determine the settings file path based on the operating system.
    """
    base_dir = os.path.join(os.getenv('LOCALAPPDATA'), app_name)
    # Ensure the directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    return os.path.join(base_dir, 'settings.json')