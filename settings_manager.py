import json
import os
from typing import Any, Dict

class AppSettings:
    def __init__(self, settings_data: Dict[str, Any] = None):
        self.data = settings_data or {}

    @classmethod
    def load_from_file(cls, file_path: str) -> 'AppSettings':
        if not os.path.exists(file_path):
            return cls()
        
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                return cls(data)
        except json.JSONDecodeError as e:
            print(f"Error loading settings file: {e}")
            return cls()

    def save_to_file(self, file_path: str):
        with open(file_path, 'w') as file:
            json.dump(self.data, file, indent=4)

    def update_settings(self, section: str, key: str, value: Any):
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value

    def get_settings(self, section: str) -> Dict[str, Any]:
        return self.data.get(section, {})

    def as_json(self) -> str:
        """
        Return the settings as a JSON string.
        """
        return json.dumps(self.data, indent=4)

def get_settings_file_path(app_name: str) -> str:
    base_dir = os.path.join(os.getenv('LOCALAPPDATA'), app_name)
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, 'settings.json')