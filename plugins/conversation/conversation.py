from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from prompt_manager import PromptManager
from context_manager import context_manager
import asyncio,json
from concurrent.futures import ThreadPoolExecutor

class Conversation(Baseplugin):  
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.conversation_is_open=False
        
    def init_timeout(self):
        print("INIT TIMEOUT")
        self.timeout = int(self.settings.get("timeout", 120000)) / 1000  # Convert milliseconds to seconds
        self.timeout_task = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.reset_timeout()

    def reset_timeout(self):
        if self.timeout_task:
            self.timeout_task.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.timeout_task = loop.create_task(self.start_timeout())

    async def start_timeout(self):
        print("Starting non-blocking timeout")
        await asyncio.sleep(self.timeout)
        # await (self.abandon_conversation())        
        # self.test_conversation()


    @hookimpl
    async def new_conversation(self):
        self.thread=[]
        self.conversation_is_open=True
        context_manager.update_context("conversation","")
        self.init_timeout()
        
    @hookimpl
    async def abandon_conversation(self,cause="timeout"):
        txt = await self.get_conversation(format="txt")
        last_conversation = {"thread": self.thread, "txt": txt}
        self.thread=[]
        context_manager.update_context("conversation","")
        self.send_message_to_frontend({"action":"abandon_conversation"})
        self.conversation=False
        print(f"Conversation abandoned for cause:{cause}")
        await self.pm.trigger_hook("after_conversation_end",last_conversation=last_conversation)
        
    @hookimpl
    async def add_msg_to_conversation(self, msg: str, author: str) -> None:
        if not(self.conversation_is_open):
            await self.new_conversation()
        print(f"Adding {msg} to conversation")
        newmsg = {"msg": msg, "author": author}
        self.thread.append(newmsg)
        self.send_message_to_frontend(json.dumps(newmsg))
        bms = {"backend": "addmsg"}
        self.send_message_to_app(json.dumps(bms))
        conv = await self.get_conversation(format="raw")
        context_manager.update_context("conversation", conv)
        self.reset_timeout()
    
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
            print(output)
            return "\n".join(output)
    
    def test_conversation(self):
        async def run_tasks():
            await self.add_msg_to_conversation("Comment s'appellent tes enfants ?", "def")
            await self.get_conversation()
            conversation_value = context_manager.get_value("conversation")
            print("Retrieved conversation from context:", conversation_value)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_tasks())
        else:
            asyncio.create_task(run_tasks())
    