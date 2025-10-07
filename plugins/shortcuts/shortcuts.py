from plugin_manager import hookimpl 
from plugins.baseplugin.baseplugin import Baseplugin
from context_manager import context_manager
from datetime import datetime
import locale
from dotenv import load_dotenv
load_dotenv()
import asyncio,json

class Shortcuts(Baseplugin):    
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.is_loaded = True
        
    @hookimpl
    def startup(self):
        print("STARTUP")
        
    def process_incoming_message(self, message):
        try:
            print("Received msg: " + message)
            # Attempt to parse the message as JSON
            message_dict = json.loads(message)
            # Output the JSON variables and values
            for key, value in message_dict.items():
                print(f"Key: {key}, Value: {value}")
            # Ensure message_dict is a dictionary
            if isinstance(message_dict, dict):
                action = message_dict.get("action")
            if action == "speak":
                msg = message_dict.get("msg")
                print (f"Speaking {msg}")
                if msg:
                    asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                    # asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master",msg_input="shortcuts"))
                else:
                    print("Speak action is present but msg is empty.")
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return