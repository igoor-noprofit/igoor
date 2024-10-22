import json
import os
from pydantic import BaseModel, ValidationError, Field

class AppSettings(BaseModel):
    theme: str = Field(default='light', description="UI Theme")
    notifications_enabled: bool = Field(default=True, description="Enable notifications")

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

def get_settings_file_path(app_name='YourAppName'):
    """
    Determine the settings file path based on the operating system.
    """
    if platform.system() == "Windows":
        base_dir = os.path.join(os.getenv('LOCALAPPDATA'), app_name)
    elif platform.system() == "Darwin":  # macOS
        base_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', app_name)
    else:  # Assume Linux or other Unix-like systems
        base_dir = os.path.join(os.path.expanduser('~'), f'.{app_name.lower()}')
    
    # Ensure the directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    return os.path.join(base_dir, 'settings.json')

# Example usage:
if __name__ == '__main__':
    settings_file = get_settings_file_path()

    # Load settings
    settings = AppSettings.load_from_file(settings_file)
    print("Current settings:", settings.as_json())

    # Update settings and save
    settings.update_setting('theme', 'dark')
    settings.save_to_file(settings_file)

    print("Updated settings:", settings.as_json())