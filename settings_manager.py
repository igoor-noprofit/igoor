import json
import os

class SettingsManager:
    def __init__(self, settings_file=None):
        self.settings_file = settings_file or os.path.join(os.getenv('APPDATA'), os.getenv("IGOOR_APPNAME"), 'settings.json')
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        """Load settings from the JSON file."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            print(f"Settings file not found at {self.settings_file}. Using default settings.")
            self.settings = {
                "user": {
                    "lang": "fr_FR",
                    "locale": "fr_FR.UTF-8"
                },
                "plugins": {}
            }
            self.save_settings()

    def save_settings(self):
        """Save settings to the JSON file."""
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)

    def get_all_settings(self):
        """Return all settings."""
        return self.settings

    def get_plugin_settings(self, plugin_name):
        """Retrieve settings for a specific plugin."""
        return self.settings.get('plugins', {}).get(plugin_name, {})

    def update_plugin_settings(self, plugin_name, new_settings):
        """Update settings for a specific plugin."""
        if 'plugins' not in self.settings:
            self.settings['plugins'] = {}
        
        if plugin_name not in self.settings['plugins']:
            self.settings['plugins'][plugin_name] = {}
        
        self.settings['plugins'][plugin_name].update(new_settings)
        self.save_settings()
        
    def as_json(self):
        """Return settings as a formatted JSON string."""
        return json.dumps(self.settings, indent=4)

    def __str__(self):
        """Define the string representation of the settings."""
        return self.as_json()
