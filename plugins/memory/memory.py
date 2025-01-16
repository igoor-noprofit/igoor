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

MEMORY_SYSTEM_PROMPT = """
Tu dois analyser une conversation pour en extraire d'éventuelles mémoires: 

- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Retourne un JSON avec:

"theme": synthétise le thème de la conversation; 
"facts": un array contenant toutes les informations pertinentes sur {bio_name}, sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.), les souvenirs de sa vie. Pour chaque fact, précise s'il s'agit d'une information de court terme ou de long terme.Il peut ne pas y avoir des faits à sauvegarder.
"tags": étiquettes pour classer la conversation et la mieux la retrouver ensuite.

Critères importants : 
- Un "fact" est une information objective et vérifiable concernant l'utilisateur ou son entourage.
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait.

Voici quelques exemples de prompt et de output JSON demandé:

----
Input: Q: Il fait beau aujourd'hui. R: Absolument.
Output: {{"theme": "météo", "tags": ["beau temps"], "facts": []}}

Input: Q: Tu as soif ? R: Oui. Q: Tu veux de l'eau ? R: Avec plaisir.
Output: {{"theme": "soif", "tags": ["eau"], "facts": []}}

Input: Q: Tu veux prendre un goûter ? R: Oui, un yaourt. Q: Nature ou aux fruits ? R: Nature, avec un peu de sucre.
Output: {{"theme":"goûter","tags":["yaourt","préférences alimentaires"],"facts":[{{"fact":"{bio_name} veut prendre un goûter","type":"short"}}]}}

Input: R: Tu peux fermer la fenetre?Tu sais que je suis frileux. Q: No problem!
Output: {{"theme": "froid", "facts" : [{{"fact":"{bio_name} est frileux"]}}

Input: Q: T'aime le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus !
Output: {{"theme":"gâteau de riz","facts":[{{"fact":"{bio_name} n'aime plus le gâteau de riz","type":"long"}}],"tags":["Préférences alimentaires","gâteau","dessert"]}}

Input: Q: Tu as eu des nouvelles d'Anatole ? R: Oui, il est rentré à Paris Q: Il va bien ? R: Oui
Output: {{"theme":"famille","tags":["Anatole","Paris","enfants"],"facts":[{{"fact":"Anatole est rentré à Paris","type":"short"}},{{"fact":"Anatole va bien","type":"short"}}]}}

Input : Q: Il m'a dit que Claire ne t'en veut pas R: T'es sur de ça ? Q: Oui R: J'en suis très soulagé
Output : {{"theme":"relations familiales","tags":["Claire","famille","enfants","Anton","Anatole","Paloma"],"facts":[{{"fact":"Claire ne lui en veut pas","type":"short"}},{{"fact":"{bio_name} est très soulagé que Claire ne lui en veut pas","type":"short"}}]}}
----

Attention: les opinions exprimées par l'utilisateur sont précédées par R:, et pas par Q:. Par exemple: 

Input: Q: J'aime la glace
Output: {{"theme":"préférences alimentaires","tags":["glace"],"facts":[]}}

En revanche:

Q: J'aime la glace R: Moi aussi!
Output: {{"theme":"préférences alimentaires","tags":["glace"],"facts":[{{"fact":"{bio_name} aime la glace","type":"long"}}]}}

Aussi,des questions posées par l'interlocuteur et qui restent sans réponses ne sont PAS des mémoires: 

Input: Q: Est-ce que tu aime les spaghetti ?
Output: {{"theme":"préférences alimentaires","tags":["spaghetti"],"facts":[]}}

---
Retourne seulement les faits et opinions dans le format JSON,sans aucune explication.
"""

PROMPT_TEMPLATE = """{conversation}"""

MEMORY_REVIEW_SYSTEM_PROMPT = """
Tu reçois un JSON avec: 

1) une conversation analysée par l'IA pour en extraire des mémoires de court et de long terme;
2) la mémoire que l'IA a détecté.

Ex: 
{{
    "conversation": " Q: T'aimes le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus ,!",
    "memory": {{
        "fact": "{bio_name} n'aime plus le gâteau de riz",
        "type": "long"
    }},
    "rag":"---{bio_name} aime les plats asiatiques,en particulier les soupes"
}}

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Dans cet exemple, l'IA reconnait justement qu'un nouvelle mémoire à long terme est à sauvegarder, 
parce qu'une évolution des préférences de l'utilisateur a été détecté.
Aussi,les informations déjà dans la base de connaissances (rag) n'indiquent pas déjà cette info.

L'IA a détecte l'information à mémoriser selon ces critères:

---
- "fact" est une information pertinente sur l'utilisateur,sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.), les souvenirs de sa vie. 
- Un "fact" est une information objective et vérifiable concernant l'utilisateur ou son entourage
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait
- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.
---

Retourne exclusivement un JSON avec:

{{"valid":true}}

si la mémoire est validée par toi.

---
La mémoire n'est pas validée:

1)si l'information ne constitue pas une mémoire de long terme;
2)si le "rag" contient déjà cette information.

Exemple de mémoire non validée:

---
Input: 
{{
    "conversation": " Q: Tu veux qu'on prépare une soupe ce soir ? R: Oui, une soupe aux légumes. Q: Avec des croûtons ? R: Oui, et un peu de fromage râpé.",
    "memory": {{
        "fact": "{bio_name} aime les croûtons dans sa soupe",
        "type": "long"
    }},
    "rag": "---{bio_name} aime les plats asiatiques---"
}}
Output:
{{"valid":false,"reason":"Nous ne savons pas si {bio_name} en général aime les croutons dans sa soupe ou si il voulait juste essayer"}}
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
        # self.test_plugin()
    
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
        
        # SYSTEM PROMPT
        sys_pm = PromptManager(template=MEMORY_SYSTEM_PROMPT)
        system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
        
        # HUMAN PROMPT
        conversation = last_conversation.get("txt")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(conversation=conversation)       
        
        # Get memories from first LLM call
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"), log_folder=self.plugin_folder)
        llm.set_json_schema(DataModel)
        memories = llm.invoke(system_prompt, prompt)
        has_error, memories = self.handle_llm_error(memories)
        if has_error:
            return memories
        # Process each memory
        if hasattr(memories, 'facts') and memories.facts:
            for memory in memories.facts:
                if memory.type == "long":
                    print(f"Reviewing long-term memory: {memory.fact}")
                    validation = await self.memory_review(conversation, memory)
                    
                    if validation.valid:
                        print(f"Memory validated, storing: {memory.fact}")
                        try:
                            await self.pm.trigger_hook(hook_name="store_memory", memory=memory.fact)
                        except Exception as e:
                            print(f"Error storing memory: {e}")
                    else:
                        print(f"Memory not validated: {validation.reason}")
            
            # Save index after all memories are processed
            await self.pm.trigger_hook("save_index")
        
        end_time = time.time()
        print(f"Total processing time: {end_time - start_time} seconds")
    

    def test_plugin(self):
        print("BEGINNING MEMORY TESTS")
        """Test the memory plugin with sample conversations"""
        test_conversations = [
            "R: Paloma a oublié de me dire comment s'est passée son exposé. Q: Je vais lui demander, elle est dans sa chambre. Q: Tu veux qu'elle te raconte ce soir pendant le dîner ? R: Oui, ça me ferait plaisir.",
            "Q: Tu veux écouter un peu de musique ? R: Oui, je veux bien. Q: Du jazz ? Tu adores ça. R: Oui, mets un peu de Iiro Rantala.",
            "Q: Il fait beau aujourd'hui. R: Absolument."
        ]
        
        def txt_to_thread(conversation_txt):
            """Convert text conversation format to thread format"""
            thread = []
            # Split by Q: or R: but keep the delimiters
            parts = [p.strip() for p in conversation_txt.replace("Q:", "\nQ:").replace("R:", "\nR:").split("\n") if p.strip()]
            
            for part in parts:
                if part.startswith("Q:"):
                    thread.append({"msg": part[2:].strip(), "author": "def"})
                elif part.startswith("R:"):
                    thread.append({"msg": part[2:].strip(), "author": "master"})  # Changed from "user" to "master"
            return thread

        async def run_tests():
            for conversation in test_conversations:
                # Convert to the expected dictionary format
                thread = txt_to_thread(conversation)
                last_conversation = {
                    "thread": thread,
                    "txt": conversation,
                    "cause": "test"
                }
                
                print(f"\nTesting conversation: {conversation}")
                try:
                    print("Converted thread:")
                    for msg in thread:
                        print(f"  {msg['author']}: {msg['msg']}")
                except Exception as e:
                    print(f"Error printing thread: {e}")
                
                try:
                    await self.after_conversation_end(last_conversation=last_conversation)
                    print("Test completed successfully")
                except Exception as e:
                    print(f"Test failed with error: {e}")
                    # Print more detailed error information
                    import traceback
                    print("Full error traceback:")
                    print(traceback.format_exc())

        # Run the tests
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(run_tests())
            
    
    
    ''' 
    Returns TRUE if memory does not exist in RAG, otherwise FALSE 
    def check_memory(memory):
        Calls LLM to double check memory before inserting into RAG    
    '''
    async def memory_review(self, conversation, memory):
        """Reviews a memory to determine if it should be stored"""
        start_time = time.time()
        
        # Get RAG context
        rag = await self.query_rag_async(memory.fact)
        
        # Convert Pydantic Fact object to dict
        memory_dict = {
            "fact": memory.fact,
            "type": memory.type
        }
        
        # Create the memory review package
        memory_to_be_checked = {
            "conversation": conversation,
            "memory": memory_dict,  # Use the dict version instead of Pydantic model
            "rag": rag
        }
        
        # Set up prompts
        sys_pm = PromptManager(template=MEMORY_REVIEW_SYSTEM_PROMPT)
        system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
        
        pm = PromptManager(template=MEMORY_REVIEW_PROMPT_TEMPLATE)
        prompt = pm.create_prompt(memory_to_be_checked=json.dumps(memory_to_be_checked))

        # Call LLM with ValidationResponse schema
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"), log_folder=self.plugin_folder)
        llm.set_json_schema(ValidationResponse)
        validation = llm.invoke(system_prompt, prompt)
        
        has_error, validation = self.handle_llm_error(validation)
        if has_error:
            return validation
        
        end_time = time.time()
        print(f"Memory review time: {end_time - start_time} seconds")
        return validation
    
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        return result
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Memory plugin received new status: {status}")

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
    reason: str = ""