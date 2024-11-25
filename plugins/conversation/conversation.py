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
        self.run_new_conversation()
    
    @hookimpl
    def startup(self):
        print("CONVERSATION STARTUP")

    @hookimpl
    async def new_conversation(self):
        self.thread=[]
        context_manager.update_context("conversation","")
    
    def run_new_conversation(self):
        if not asyncio.get_event_loop().is_running():
            asyncio.run(self.new_conversation())
        else:
            asyncio.create_task(self.new_conversation())

    '''
    ABANDON CONVERSATION EVENT
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
            if isinstance(message_dict, dict) and message_dict.get("action") == "abandon":
                self.run_new_conversation()
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return

    @hookimpl
    async def add_msg_to_conversation(self, msg: str, author: str) -> None:
        newmsg = {"msg": msg, "author": author}
        self.thread.append(newmsg)
        self.send_message_to_frontend(json.dumps(newmsg))
        conv = await self.get_conversation(format="raw")
        context_manager.update_context("conversation", conv)
    
    @hookimpl
    async def delete_conversation(self):
        self.thread=[]
        
    @hookimpl
    async def get_conversation(self, format="json"):
        if format == "json":
            return self.thread
        else:
            output = []
            for message in self.thread:
                if message["author"] == "def":
                    output.append(f"Q: {message['msg']}")
                else:
                    output.append(f"R: {message['msg']}")
            return "\n".join(output)
        
    '''
        
    @hookimpl
    def activate(self):
        print ("Activating conversation")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating conversation") 
    '''

    