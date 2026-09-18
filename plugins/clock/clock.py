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
        self.mark_ready()
        
    @hookimpl
    def startup(self):
        self.formatted_date_time = ""
        # Get locale from onboarding plugin settings
        loc = self.settings_manager.get_nested(["plugins", "onboarding", "prefs", "locale"])
        
        # Set locale if found, otherwise log a warning and use system default
        if loc:
            # Try several forms: raw, encoding-suffixed (Linux), and a
            # corrected region (handles invalid locales like 'en_EN')
            lang = loc.split("_")[0].lower() if "_" in loc else None
            default_region = {"en": "en_US", "fr": "fr_FR", "it": "it_IT", "es": "es_ES", "de": "de_DE", "nl": "nl_NL", "pt": "pt_PT"}.get(lang)
            candidates = [loc, f"{loc}.UTF-8"]
            if default_region:
                candidates += [default_region, f"{default_region}.UTF-8"]
            for cand in candidates:
                try:
                    locale.setlocale(locale.LC_TIME, cand)
                    if cand != loc:
                        self.logger.info(f"Locale '{loc}' unavailable, using '{cand}'")
                    break
                except locale.Error:
                    continue
            else:
                self.logger.error(f"No usable locale among {candidates}. Using system default.")
                try:
                    locale.setlocale(locale.LC_TIME, '')
                except locale.Error:
                    self.logger.error("Could not set system default locale.")
        else:
            self.logger.warning("Locale not found in settings, using system default.")
            # Attempt to set to default locale, might vary by system
            try:
                locale.setlocale(locale.LC_TIME, '')
            except locale.Error:
                self.logger.error("Could not set system default locale.")
        self.update_date_time()
        
    def update_date_time(self):
        now = datetime.now()

        # Formatting date with locale
        date_string = now.strftime("%A, %d %B %Y")

        # Formatting time with locale
        time_string = now.strftime("%H:%M")  # 24-hour format (change to %I:%M %p for 12-hour format)

        self.formatted_date_time = f"{date_string} {time_string}"
        # print ("DATETIME: ", self.formatted_date_time)
        context_manager.update_context("current_datetime", self.formatted_date_time)