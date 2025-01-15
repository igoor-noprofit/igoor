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
Tu dois analyser une conversation pour en extraire d'éventuelles mémoires: 

- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Retourne un JSON avec:

“theme”: synthétise le thème de la conversation; 
“facts”: un array contenant toutes les informations pertinentes sur {bio_name}, sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.), les souvenirs de sa vie. Pour chaque fact, précise s'il s'agit d'une information de court terme ou de long terme.Il peut ne pas y avoir des faits à sauvegarder.
“tags”: étiquettes pour classer la conversation et la mieux la retrouver ensuite.

Critères importants : 
- Un “fact” est une information objective et vérifiable concernant l'utilisateur ou son entourage.
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait.

Voici quelques exemples de prompt et de output JSON demandé:

----
Input: Q: Il fait beau aujourd'hui. R: Absolument.
Output: {"theme": "météo", "tags": ["beau temps"], "facts": []}

Input: Q: Tu as soif ? R: Oui. Q: Tu veux de l'eau ? R: Avec plaisir.
Output:  {"theme": "soif", "tags": ["eau"], "facts": []}

Input: Q: Tu veux prendre un goûter ? R: Oui, un yaourt. Q: Nature ou aux fruits ? R: Nature, avec un peu de sucre.
{"theme":"goûter","tags":["yaourt","préférences alimentaires"],"facts":[{"fact":"{bio_name} veut prendre un goûter","type":"short"}]}

Input: R: Tu peux fermer la fenetre?Tu sais que je suis frileux. Q: No problem!
Output: {{"facts" : ["{bio_name} est frileux"]}}

Input: Q: T'aime le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus !
Output: {"theme":"gâteau de riz","facts":[{"fact":"{bio_name} n'aime plus le gâteau de riz","type":"long"}],"tags":["Préférences alimentaires","gâteau","dessert"]}

Input: Q: Tu as eu des nouvelles d'Anatole ? R: Oui, il est rentré à Paris Q: Il va bien ? R: Oui
Output: {"theme":"famille","tags":["Anatole","Paris","enfants"],"facts":[{"fact":"Anatole est rentré à Paris","type":"short"},{"fact":"Anatole va bien","type":"short"}]}

Input : Q: Il m'a dit que Claire ne t'en veut pas R: T'es sur de ça ? Q: Oui R: J'en suis très soulagé
Output : {"theme":"relations familiales","tags":["Claire","famille","enfants","Anton","Anatole","Paloma"],"facts":[{"fact":"Claire ne lui en veut pas","type":"short"},{"fact":"{bio_name} est très soulagé que Claire ne lui en veut pas","type":"short"}]}
----

Attention: les opinions exprimées par l'utilisateur sont précédées par R:, et pas par Q:. Par exemple: 

Q: J'aime la glace

Ne veut absolument pas dire que l'utilisateur aime la glace. En revanche:

Q: J'aime la glace R: Moi aussi!

Veut dire que l'utilisateur aime la glace.

Retourne seulement les faits et opinions dans le format JSON,sans aucune explication.
"""

PROMPT_TEMPLATE = """{conversation}"""

MEMORY_REVIEW_SYSTEM_PROMPT = """
Tu reçois un JSON avec: 

1) une conversation analysée par l'IA pour en extraire des mémoires de court et de long terme;
2) la mémoire que l'IA a détecté.

Ex: 
{
    "conversation": " Q: T'aimes le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus ,!",
    "memory": {
        "fact": "{bio_name} n'aime plus le gâteau de riz",
        "type": "long"
    }
    "rag":"---{bio_name} aime les plats asiatiques,en particulier les soupes"
}

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Dans cet exemple, l'IA reconnait justement qu'un nouvelle mémoire à long terme est à sauvegarder, 
parce qu'une évolution des préférences de l'utilisateur a été détecté.
Aussi,les informations déjà dans la base de connaissances (rag) n'indiquent pas déjà cette info.

L'IA a détecte l'information à mémoriser selon ces critères:

---
- “fact” est une information pertinente sur l'utilisateur,sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.), les souvenirs de sa vie. 
- Un “fact” est une information objective et vérifiable concernant l'utilisateur ou son entourage
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait
- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.
---

Retourne exclusivement un JSON avec:

{"valid":true}

si la mémoire est validée par toi.

---
La mémoire n'est pas validée:

1)si l'information ne constitue pas une mémoire de long terme;
2)si le "rag" contient déjà cette information.

Exemple de mémoire non validée:

---
Input: 
{
    "conversation": " Q: Tu veux qu'on prépare une soupe ce soir ? R: Oui, une soupe aux légumes. Q: Avec des croûtons ? R: Oui, et un peu de fromage râpé.",
    "memory": {
        "fact": "{bio_name} aime les croûtons dans sa soupe",
        "type": "long"
    },
    "rag": "---{bio_name} aime les plats asiatiques---"
}
Output:
{"valid":false,"reason":"Nous ne savons pas si {bio_name} en général aime les croutons dans sa soupe ou si il voulait juste essayer"}

"""

MEMORY_REVIEW_PROMPT_TEMPLATE = """{memory_to_be_checked}"""

class Memory(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.is_loaded = True
        
    
    @hookimpl
    def startup(self):
        loop = asyncio.get_event_loop()
        '''
        if loop.is_running():
            # If the loop is already running, use create_task
            asyncio.create_task(self.test_after_conversation_end())
        else:
            # If no loop is running, start a new one
            loop.run_until_complete(self.test_after_conversation_end())
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
        system_prompt = MEMORY_SYSTEM_PROMPT
        sys_pm=PromptManager(template=MEMORY_SYSTEM_PROMPT)
        system_prompt=sys_pm.create_prompt(bio_name=self.bio_name)
        print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(conversation=conversation)       
        print(f"FINAL MEMORY PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"),log_folder=self.plugin_folder)
        llm.set_json_schema(DataModel)
        memories = llm.invoke(system_prompt, prompt)
        print(f"TYPE = {type(memories)}, MEMORIES: {memories}")
        
        '''
        memories_dict = memories.dict()
        print(f"TYPE = {type(memories_dict)}, MEMORIES: {memories_dict}")
        
        if memories_dict.get("facts"):
            for memory in memories_dict["facts"]:  # Use "facts" here
                if (self.check_memory(conversation,memory))
                print(f"storing {memory}")
                try:
                    result = await self.pm.trigger_hook(hook_name="store_memory", memory=memory)
                except Exception as e:
                    print(f"Exception occurred while storing fact '{memory}': {e}")
            await self.pm.trigger_hook("save_index")
        '''
        end_time = time.time()
        
        print(f"Time taken for processing: {end_time - start_time} seconds")
    
    def test(self):
        
    
    
    ''' 
    Returns TRUE if memory does not exist in RAG, otherwise FALSE 
    def check_memory(memory):
        Calls LLM to double check memory before inserting into RAG    
    '''
    async def check_memory(self,conversation,memory):
        start_time = time.time()
        rag = await(self.query_rag_async(memory.fact))
        memory_to_be_checked=dict(conversation=conversation,memory=memory)
        system_prompt = MEMORY_REVIEW_SYSTEM_PROMPT
        
        print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(static_context=static_context, conversation=conversation, bio_name=self.bio_name)       
        print(f"FINAL MEMORY PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"),log_folder=self.plugin_folder)
        llm.set_json_schema(DataModel)
        memories = llm.invoke(system_prompt, prompt)
        print(f"TYPE = {type(memories)}, MEMORIES: {memories}")
        memories_dict = memories.dict()
        print(f"TYPE = {type(memories_dict)}, MEMORIES: {memories_dict}")
        
        if memories_dict.get("facts"):
            for memory in memories_dict["facts"]:  # Use "facts" here
                # self.check_memory(memory)
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
        print(f"Memory plugin received new status: {status}")
        
    
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

# Pydantic
# MEMORY TEMPLATE
class Fact(BaseModel):
    fact: str
    type: str

class DataModel(BaseModel):
    theme: str
    tags: List[str]
    facts: List[Fact]
    
# MEMORY REVIEWER TEMPLATE
class ValidationResponse(BaseModel):
    valid: bool
    reason: str