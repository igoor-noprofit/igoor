from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from context_manager import context_manager
from settings_manager import SettingsManager
import asyncio,json,time


class Autocomplete(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
    
    @hookimpl
    def startup(self):
        print("AUTOCOMPLETE STARTUP")
    
    ''' 
    @hookimpl
    def abandon_conversation(self):
        self.clear_input()
        
    @hookimpl
    def restart_asr(self):
        self.clear_input()
        
    def clear_input(self):
        self.send_message_to_frontend({"action":"clear"})
        
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
                        asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master"))
                    else:
                        print("Speak action is present but msg is empty.")
                elif message_dict.get("msg"):
                    input_value = message_dict.get("msg")
                    if input_value:
                        asyncio.create_task(self.predict(input_value))
                    else:
                        print("Input key is present but empty.")
            else:
                print("Message is not a valid dictionary.")
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
            
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
        
    '''
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")