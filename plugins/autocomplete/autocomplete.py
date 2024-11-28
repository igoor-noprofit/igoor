from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from prompts import AssistantPrompts
from settings_manager import SettingsManager
from llm_manager import LLMManager
import asyncio,json,time

PROMPT_TEMPLATE = """
Utiliser le contexte statique extrait des documents sur la vie de la personne :

{static_context}

---
Utilise aussi les infos du contexte dynamique suivant :

{dynamic_context}

---

S'il y a une conversation en cours donne la priorité à la conversation en cours.
Prédis la suite de: {input}
"""

class Autocomplete(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=AssistantPrompts("locales/","fr_FR")
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
    
    @hookimpl
    def startup(self):
        print("AUTOCOMPLETE STARTUP")

    def process_incoming_message(self, message):
        try:
            print("Received msg: " + message)
            # Attempt to parse the message as JSON
            message_dict = json.loads(message)
            # Output the JSON variables and values
            for key, value in message_dict.items():
                print(f"Key: {key}, Value: {value}")
            # Ensure message_dict is a dictionary
            if isinstance(message_dict, dict) and message_dict.get("msg"):
                input_value = message_dict.get("msg")
                if input_value:
                    asyncio.create_task(self.predict(input_value))
                else:
                    print("Input key is present but empty.")
            
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
        
    '''
    Receives msg from autocomplete input
    Transmits it to RAG systems
    Retrieves context
    Fills prompt
    Performs LLM query
    '''
    async def predict(self, msg: str) -> None:
        start_time = time.time()
        print("AUTOCOMPLETE PREDICTIONS")
        dynamic_context = self.get_dynamic_context()
        print(f"DYNAMIC CONTEXT IS {dynamic_context}")
        conversation = dynamic_context.get("conversation")
        print(f"CONVERSATION IS : {conversation}")
        assistant_type = "autocomplete"
        static_context = await(self.query_rag_async(msg))
        # print(f"STATIC CONTEXT IS : {static_context}")
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        # print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(static_context=static_context, dynamic_context=dynamic_context, input=msg)       
        print(f"FINAL HUMAN PROMPT : {prompt}")
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