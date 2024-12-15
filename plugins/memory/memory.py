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
from langchain_core.messages.ai import AIMessage
from pydantic import BaseModel
from typing import List

MEMORY_SYSTEM_PROMPT= """
Tu recevras une conversation à analyser.Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé Igor). Extrais toutes les informations pertinentes sur l'utilisateur, sa famille, ses amis, ses préférences (alimentaires, politiques,artistiques etc.),les souvenirs de sa vie. 
Voici quelques exemples de prompt et de output JSON demandé:

----
Input: Q: Il fait beau aujourd'hui. R: Absolument.
Output: {{"facts" : []}}

Input: Q: Tu as soif ? R: Oui. Q: Tu veux de l’eau ? R: Avec plaisir.
Output: {{"facts" : []}}

Input: Q: T'aime le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus !
Output: {{"facts" : ["Igor n'aime plus le gâteau de riz"]}}

Input: Q: Tu as eu des nouvelles d'Anatole ? R: Oui, il est rentré à Paris Q: Il va bien ? R: Oui
Output: {{"facts" : ["Anatole est rentré à Paris", "Anatole va bien"]}}

Input : Q: Il m'a dit que Claire ne t'en veut pas R: T'es sur de ça ? Q: Oui R: J'en suis très soulagé
{{"facts" : ["Claire n'en veut pas à Igor", "Igor est très soulagé que Claire lui en veut pas”]}}
----

Retourne les faits et opinions dans le format JSON ci-dessus.Si ces infos sont déjà présentes dans le contexte ci-dessous, 
retourne juste :

Output: {{"facts" : []}}

Attention: les opinions exprimées par l'utilisateur sont précédées par R:, et pas par Q:. Par exemple: 

Q: J'aime la glace

Ne veut absolument pas dire que l'utilisateur aime la glace. En revanche:

Q: J'aime la glace R: Moi aussi!

Veut dire que l'utilisateur aime la glace.

"""

PROMPT_TEMPLATE = """
Compare les informations de la conversation avec le contexte ci-dessous. Si le contexte contient déjà ces infos,
retourne juste

Output: {{"facts" : []}}
Contexte:
---

{static_context}

---
Conversation à analyser: {conversation}
"""

class Memory(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
    
    @hookimpl
    def startup(self):
        loop = asyncio.get_event_loop()
        '''
        if loop.is_running():
            # If the loop is already running, use create_task
            asyncio.create_task(self.test_after_conversation_end())
        else:
            # If no loop is running, start a new one
            loop.run_until_complete(self.test_after_conversation_end())ù
        '''
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    
    async def _startup_async(self):
        
        # await self.wait_for_socket_and_send("ready")
        await self.test_after_conversation_end()

    '''
    Receives last_conversation from conversation.py
    Retrieves static context
    Fills prompt
    Performs LLM query
    Stores results 
    '''
    @hookimpl
    async def after_conversation_end(self, last_conversation: dict) -> None:
        start_time = time.time()
        conversation = last_conversation.get("txt")
        static_context = await(self.query_rag_async(conversation))
        system_prompt = MEMORY_SYSTEM_PROMPT
        print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(static_context=static_context, conversation=conversation)       
        print(f"FINAL MEMORY PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"),log_folder=self.plugin_folder)
        llm.set_json_schema(Facts)
        memories = llm.invoke(system_prompt, prompt)
        print(f"TYPE = {type(memories)}, MEMORIES: {memories}")
        memories_dict = memories.dict()
        print(f"TYPE = {type(memories_dict)}, MEMORIES: {memories_dict}")
        
        if memories_dict.get("facts"):
            for memory in memories_dict["facts"]:  # Use "facts" here
                print(f"storing {memory}")
                try:
                    result = await self.pm.trigger_hook(hook_name="store_memory", memory=memory)
                except Exception as e:
                    print(f"Exception occurred while storing fact '{memory}': {e}")
            await self.pm.trigger_hook("save_index")
        end_time = time.time()
        print(f"Time taken for processing: {end_time - start_time} seconds")
        
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        return result
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
        
    
    def test_queries(self) -> None:
        queries = [
            "Q: Comment s'appelle tes fils",
            "Q: Tu te souviens de l'expo Drosephilia",
            "Q: Combien d'enfants tu as",
            "Q: Comment s'appelle ta femme",
            "Q: Quels sont tes réalisateurs préférés",
            "Q: Est-ce que t'aimes Tarantino"
        ]
        for query in queries:
            asyncio.run(self.asr_msg(query))
    
    
    '''
        
    @hookimpl
    def activate(self):
        print ("Activating flow")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating FLOW") 
    '''

# Pydantic
class Facts(BaseModel):
    facts: List[str]
