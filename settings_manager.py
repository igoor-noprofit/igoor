from version import __appname__, __version__, __codename__
import json
import os
import asyncio
import shutil
import glob
from datetime import datetime
from utils import resource_path, setup_logger

class SettingsManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    ''' 
    HANDLES global app settings.json file with all the plugins settings, api keys etc.
    '''
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.logger = setup_logger('sm', os.path.join(os.getenv('APPDATA'), __appname__))
        self.settings_file = os.path.join(os.getenv('APPDATA'), __appname__, 'settings.json')
        start_lang = os.getenv('IGOOR_START_LANG', 'en_EN')
        locale_settings_path = os.path.join('locales', start_lang, 'default_settings.json')
        default_settings_path = resource_path(locale_settings_path)
        if not os.path.exists(default_settings_path):
            fallback_settings_path = resource_path(os.path.join('locales', 'en_EN', 'default_settings.json'))
            if os.path.exists(fallback_settings_path):
                default_settings_path = fallback_settings_path
            else:
                raise FileNotFoundError('Default settings file not found for en_EN locale')
        self.default_settings_file = default_settings_path
        self.ensure_settings_file_exists()
        self.settings = self.load_settings()
        self.create_backup()

    def ensure_settings_file_exists(self):
        """Create settings.json from default if it doesn't exist"""
        if not os.path.exists(self.settings_file):
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            
            try:
                # Load default settings using resource_path
                with open(self.default_settings_file, 'r', encoding='utf-8') as f:
                    default_settings = json.load(f)
                
                # Create user settings file
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(default_settings, f, indent=4)
                    
            except Exception as e:
                self.logger.error(f"Error creating settings file from default: {e}")
                # Create minimal settings structure if default file can't be loaded
                default_settings = {
                    "plugins": {},
                    "plugins_activation": {
                        "conversation": True,  # Essential plugins
                        "ttsdefault": True
                    }
                }
                with open(self.settings_file, 'w', encoding='utf-8') as f:
                    json.dump(default_settings, f, indent=4)

    def get_prefs(self):
        return self.get_nested(["plugins", "onboarding", "prefs"], default={})
    
    def get_lang(self):
        prefs = self.get_prefs()
        return prefs.get("lang")
    
    def get_bio(self):
        return self.get_nested(["plugins", "onboarding", "bio"], default={})
    
    def get_health_state(self):
        bio = self.get_nested(["plugins", "onboarding", "bio"], default={})
        return bio.get("health_state")

    def get_nested(self, keys, default=None):
        """Retrieve a nested value from the settings dictionary."""
        data = self.settings
        for key in keys:
            # print(f"Current data: {data}")  # Debugging line
            try:
                data = data[key]
            except (TypeError, KeyError):
                print(f"Key {key} not found. Returning default: {default}")  # Debugging line
                return default
        # print(f"Final data: {data}")  # Debugging line
        return data

    def create_backup(self):
        """Create timestamped backup of settings.json, keeping only 5 most recent."""
        if not os.path.exists(self.settings_file):
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{self.settings_file}.backup.{timestamp}"

        try:
            shutil.copy2(self.settings_file, backup_file)
            self.logger.info(f"Created settings backup: {backup_file}")
        except Exception as e:
            self.logger.error(f"Error creating settings backup: {e}")

        try:
            backups = sorted(glob.glob(f"{self.settings_file}.backup.*"), reverse=True)
            for old_backup in backups[5:]:
                os.remove(old_backup)
                self.logger.info(f"Removed old backup: {old_backup}")
        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}")

    def load_settings(self):
        """Load settings with fallback: main file -> most recent backup -> defaults."""
        if not os.path.exists(self.settings_file):
            self.logger.warning(f"Settings file not found at {self.settings_file}. Using default settings.")
            with open(self.default_settings_file, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
            self.save_settings()
            return self.settings

        # Try main settings file
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
            return self.settings
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Main settings file corrupted: {e}")

        # Try most recent backup
        backups = sorted(glob.glob(f"{self.settings_file}.backup.*"), reverse=True)
        for backup_file in backups:
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                self.logger.warning(f"Loaded from backup: {backup_file}")
                # Restore corrupted file from backup
                shutil.copy2(backup_file, self.settings_file)
                return self.settings
            except (json.JSONDecodeError, IOError):
                continue

        # Fallback to default settings - preserve corrupted file first
        self.logger.error("All backups corrupted or missing. Using default settings.")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        corrupted_backup = f"{self.settings_file}.corrupted.{timestamp}"
        try:
            shutil.copy2(self.settings_file, corrupted_backup)
            self.logger.info(f"Preserved corrupted settings file: {corrupted_backup}")
        except Exception as e:
            self.logger.error(f"Error preserving corrupted file: {e}")

        # Load defaults and overwrite settings.json
        with open(self.default_settings_file, 'r', encoding='utf-8') as f:
            self.settings = json.load(f)
        self.save_settings()
        return self.settings

    def get_settings(self):
        """Return all settings (alias for get_all_settings)."""
        return self.settings

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
        #self.logger.info(f"----------------UPDATED GLOBAL SETTINGS: {self.settings}")
        self.save_settings()
        
    def save_settings(self, settings=None):
        try:
            """Save settings to the JSON file."""
            if settings is not None:
                self.settings = settings
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            # self.logger.info(f"*********** Saving settings as: {self.settings}")
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
                return True
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            return False
    
    def load_and_notify(self, plugin_manager=None):
        """Load settings from disk and notify all plugins via global_settings_updated hook."""
        self.settings = self.load_settings()
        if plugin_manager:
            asyncio.create_task(plugin_manager.trigger_hook('global_settings_updated'))
        return self.settings
        
    def as_json(self):
        """Return settings as a formatted JSON string."""
        return json.dumps(self.settings, indent=4)

    def __str__(self):
        """Define the string representation of the settings."""
        return self.as_json()
