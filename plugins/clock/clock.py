from plugin_manager import hookimpl 
from app import context_manager
from datetime import datetime
import locale
from dotenv import load_dotenv
load_dotenv()
import os

class Clock:
    @hookimpl
    def get_frontend_components(self):
        print("loading datetime frontend")
        return [
            {
                "vue": "datetime_component.vue"
            }
        ]
    
    @hookimpl
    def startup(self):
        print ("Starting CLOCK plugin")
        self.formatted_date_time = ""
        # Set locale if provided, otherwise use system default
        loc = os.getenv("IGOOR_LOCALE") # check in context, env or others
        locale.setlocale(locale.LC_TIME, loc)
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