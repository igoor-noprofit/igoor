from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from prompts import AssistantPrompts
from settings_manager import SettingsManager
from llm_manager import LLMManager
import asyncio,json,time,os

PROMPT_TEMPLATE = """
Pour répondre tu peux utilisers le contexte statique extrait des documents sur la vie de la personne :

{static_context}

---
Si besoin utilise aussi les infos du contexte dynamique suivant :

{dynamic_context}
---

"""

class Daily(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=AssistantPrompts("locales/","fr_FR")
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        self.daily_data = None
        
    def load_daily_data(self):
        daily_file = os.path.join(self.plugin_folder, 'daily.json')
        print(f"DAILY FILE PATH: {daily_file}")
        try:
            with open(daily_file, 'r', encoding='utf-8') as f:
                self.daily_data = json.load(f)
                print(self.daily_data)
                return True
        except FileNotFoundError:
            print ("ERROR DAILY JSON NOT FOUND")
            current_file_dir = os.path.dirname(__file__)
            default_daily_file = os.path.join(current_file_dir, 'daily.json')
            print(f"USING DEFAULT DAILY FROM {default_daily_file}")
            with open(default_daily_file, 'r', encoding='utf-8') as f:
                self.daily_data = json.load(f)
            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump(self.daily_data, f, ensure_ascii=False, indent=4)
                print(f"Daily.json copied from {current_file_dir} to {self.plugin_folder}")
    
    @hookimpl
    def startup(self):
        print("DAILY STARTUP")
        self.load_daily_data()
    
    async def startup_async(self):
        """Async startup tasks"""
        print("DAILY ASYNC STARTUP")
        await self.send_message_to_frontend({
            'dailyData': self.daily_data
        })

    def process_incoming_message(self, message):
        try:
            message_data = json.loads(message)
            print(f"DAILY BACKEND RECEIVED MSG On WS: {message_data}")
            if message_data.get('socket') == 'ready':
                print(self.daily_data)
                # Send daily data to frontend
                self.send_message_to_frontend({
                    'dailyData': self.daily_data
                })
            elif message_data.get('action') == 'cardClicked':
                # Handle card click events
                pass
        except json.JSONDecodeError:
            print(f"Invalid JSON message received: {message}")
        
    '''
    Receives msg from speaker
    Transmits it to RAG systems
    Retrieves context
    Fills prompt
    Performs LLM query
    '''
    @hookimpl
    async def asr_msg(self, msg: str) -> None:
        start_time = time.time()
        dynamic_context = self.get_dynamic_context().copy()
        print(f"DYNAMIC CONTEXT IS {dynamic_context}")
        # Remove the conversation attribute from dynamic context
        conversation = dynamic_context.get("conversation")
        static_context = await(self.query_rag_async(conversation))
        # print(f"STATIC CONTEXT IS : {static_context}")
        del dynamic_context["conversation"]
        assistant_type = "flow"
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        # print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        dynamic_context = dynamic_context
        prompt = pm.create_prompt(static_context=static_context, dynamic_context=dynamic_context, conversation=conversation)       
        print(f"FINAL PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
        answers = llm.invoke(system_prompt,prompt)
        end_time = time.time()
        print(f"Time taken for processing: {end_time - start_time} seconds")
        self.send_message_to_frontend(answers.content) 
        
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        return result
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
