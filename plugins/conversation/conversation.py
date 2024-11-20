from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from prompt_manager import PromptManager
from context_manager import context_manager
import asyncio,json

class Conversation(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.settings = self.get_my_settings()
        self.thread=[]
    
    @hookimpl
    def startup(self):
        print("CONVERSATION STARTUP")

    
    '''
    def process_incoming_message(self, message):
        try:
            print("Received msg: " + message)
            # Attempt to parse the message as JSON
            message_dict = json.loads(message)
            # Output the JSON variables and values
            for key, value in message_dict.items():
                print(f"Key: {key}, Value: {value}")
            # Ensure message_dict is a dictionary
            if isinstance(message_dict, dict) and message_dict.get("action") == "speak":
                msg = message_dict.get("msg", "")
                # Trigger hook in plugin manager with msg
                asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
            
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
    '''
    
    '''
    Receives msg from speaker
    Transmits it to RAG systems
    Performs query
    '''
    @hookimpl
    async def add_msg_to_conversation(self, msg: str, author: str) -> None:
        newmsg = {"msg": msg, "author": author}
        self.thread.append(newmsg)
        self.send_message_to_frontend(json.dumps(newmsg))
    
    @hookimpl
    async def delete_conversation(self):
        self.thread=[]
    
    '''
        
    @hookimpl
    def activate(self):
        print ("Activating flow")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating FLOW") 
    '''

    