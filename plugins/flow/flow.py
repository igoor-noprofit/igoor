from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from prompts import AssistantPrompts
from settings_manager import SettingsManager
from llm_manager import LLMManager


PROMPT_TEMPLATE = """
{system_prompt}

Réponds en utilisant aussi le contexte statique suivant:

{static_context}

---
Si besoin utilise les infos du contexte dynamique suivant :

{dynamic_context}

Réponds en utilisant aussi le contexte ci-dessus à la question: {question}
"""

class Flow(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=AssistantPrompts("locales/","fr_FR")
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        
        # self.status_manager.register_observer(self)  # Register this plugin as an observer

    '''
    Receives msg from speaker
    Transmits it to RAG systems
    
    '''
    @hookimpl
    async def asr_msg(self, msg: str) -> None:
        print(f"QUERYING RAG WITH: {msg}")
        static_context = await(self.query_rag_async(msg))
        print(f"STATIC CONTEXT IS : {static_context}")
        dynamic_context = self.get_dynamic_context()
        print(f"DYNAMIC CONTEXT IS : {dynamic_context}")
        assistant_type="flow"
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm=PromptManager(template=PROMPT_TEMPLATE)
        prompt=pm.create_prompt(system_prompt=system_prompt,static_context=static_context,dynamic_context=dynamic_context, question=msg)       
        print(f"FINAL PROMPT : {prompt}")
        llm=LLMManager(self.settings.get("provider"),self.settings.get("api_key"),self.settings.get("model_name"))
        answers=llm.invoke(prompt)
        print(answers.content)
        
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        # Await the async hook call
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        return result
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
        
    
    '''
    @hookimpl
    def startup(self):
        print("STARTUPSELF")
        
    @hookimpl
    def activate(self):
        print ("Activating flow")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating FLOW") 
    '''
    