from plugin_manager import hookimpl 
from plugins.baseplugin.baseplugin import Baseplugin
from context_manager import context_manager
from datetime import datetime
import locale
from dotenv import load_dotenv
load_dotenv()
import os

class Clock(Baseplugin):    
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.is_loaded = True
        
    @hookimpl
    def startup(self):
        self.formatted_date_time = ""
        # Get locale from onboarding plugin settings
        loc = self.settings_manager.get_nested(["plugins", "onboarding", "prefs", "locale"])
        
        # Set locale if found, otherwise log a warning and use system default
        try:
            if loc:
                locale.setlocale(locale.LC_TIME, loc)
            else:
                self.logger.warning("Locale not found in settings, using system default.")
                # Attempt to set to default locale, might vary by system
                try:
                    locale.setlocale(locale.LC_TIME, '') 
                except locale.Error:
                    self.logger.error("Could not set system default locale.")
        except locale.Error as e:
            self.logger.error(f"Failed to set locale to '{loc}': {e}. Using system default.")
            # Attempt to set to default locale as a fallback
            try:
                locale.setlocale(locale.LC_TIME, '')
            except locale.Error:
                self.logger.error("Could not set system default locale as fallback.")
        self.update_date_time()
        
    def update_date_time(self):
        now = datetime.now()

        # Formatting date with locale
        date_string = now.strftime("%A, %d %B %Y")

        # Formatting time with locale
        time_string = now.strftime("%H:%M")  # 24-hour format (change to %I:%M %p for 12-hour format)

        self.formatted_date_time = f"{date_string} {time_string}"
        # print ("DATETIME: ", self.formatted_date_time)
        context_manager.update_context("horaire", self.formatted_date_time)