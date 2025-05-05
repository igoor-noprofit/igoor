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
from utils import normalize_filter_by_timeframe_result

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
Output : {{"theme":"relations familiales","tags":["Claire","famille"],"facts":[{{"fact":"Claire ne lui en veut pas","type":"short"}},{{"fact":"{bio_name} est très soulagé que Claire ne lui en veut pas","type":"short"}}]}}
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
2) la mémoire de long terme que l'IA a détecté.

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
Aussi,les informations déjà dans la base de connaissances (rag) n'indiquent PAS déjà cette info.

L'IA a détecte l'information à mémoriser selon ces critères:

---
- "fact" est une information pertinente sur l'utilisateur,sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.)
- Un "fact" est une information objective et vérifiable concernant l'utilisateur ou son entourage ou des opinions "stables" de l'utilisateur
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait
- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.
---

Exemple de output de mémoire validée:

{{"valid":true,"reason":"Une évolution des préférences de {bio_name} a été détecté"}}

reason doit indiquer la raison pour laquelle la mémoire est validée.

La mémoire peut etre validée meme si le RAG contient déjà une info complémentaire différente (ex. "aime le riz" est compatible avec "aime les spaghetti").

---
La mémoire n'est AP validée:

1)si l'information ne constitue pas une mémoire de long terme
2)si le RAG contient déjà une information identique ou très semblable: donc inutile de la réiterer   

Exemple de mémoires NON validées:

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

Input: 
{{
    "conversation": "R: que tu aimes le jazz?",
    "memory": {{
        "fact": "{bio_name} aime le jazz",
        "type": "long"
    }}
}}
Output:
{{"valid":false,"reason":"La question n'est pas claire et l'utilisateur n'a pas répondu"}}

Input: 
{{
    "conversation": "Q: J'aime de plus en plus le jazz",
    "memory": {{
        "fact": "{bio_name} aime le jazz",
        "type": "long"
    }},
    "rag": "---Préférences artistiques de {bio_name}: il adore le jazz---"
}}
Output:
{{"valid":false,"reason":"c'est déjà établi dans ses préférences artistiques, pas besoin de le répéter"}}
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
    Helper function to store memory via hook
    '''
    async def store_memory_via_hook(self, memory, memories, reason, conversation_id):
        try:
            self.logger.debug(f"Triggering store_memory hook with conversation_id: {conversation_id}")
            await self.pm.trigger_hook(
                hook_name="store_memory",
                fact=memory.fact,
                type=memory.type,
                theme=memories.theme,
                tags=memories.tags,
                reason=reason,
                conversation_id=conversation_id,
                created_at=time.time() # Add current timestamp
            )
        except Exception as e:
            self.logger.error(f"Error storing memory: {e}")

    '''
    Receives last_conversation from conversation.py
    Retrieves static context
    Fills prompt
    Performs LLM query
    Stores memories if any 
    '''
    @hookimpl
    async def after_conversation_end(self, last_conversation: dict) -> None:
        start_time = time.time()
        
        # Get conversation ID if available and log it
        conversation_id = last_conversation.get("thread_id")
        self.logger.info(f"Processing conversation end with ID: {conversation_id}")
        
        if conversation_id is None:
            self.logger.warning("No conversation_id found in last_conversation")
            self.logger.debug(f"last_conversation contents: {last_conversation}")
        
        # SYSTEM PROMPT
        sys_pm = PromptManager(template=MEMORY_SYSTEM_PROMPT)
        system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
        
        # HUMAN PROMPT
        conversation = last_conversation.get("txt")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(conversation=conversation)       
        
        try:
            # Get memories from first LLM call
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"), log_folder=self.plugin_folder)
            llm.set_json_schema(DataModel)
            memories = llm.invoke(system_prompt, prompt)
            has_error, memories = self.handle_llm_error(memories)
            if has_error:
                self.logger.error(f"Error getting memories: {memories}")
                return memories
            
            # Process each memory
            if hasattr(memories, 'facts') and memories.facts:
                for memory in memories.facts:
                    # For long-term memories, validate first
                    if memory.type == "long":
                        self.logger.info(f"Reviewing long-term memory: {memory.fact}")
                        validation = await self.memory_review(conversation, memory)
                        
                        if validation.valid or self.settings.get("review", True) is False:
                            self.logger.info(f"Memory validated, storing: {memory.fact} with conversation_id: {conversation_id}")
                            await self.store_memory_via_hook(memory, memories, validation.reason, conversation_id)
                        else:
                            self.logger.info(f"Memory not validated: {validation.reason}")
                    else:
                        # Store short-term memories without validation
                        self.logger.info(f"Storing short-term memory: {memory.fact} with conversation_id: {conversation_id}")
                        await self.store_memory_via_hook(memory, memories, "short", conversation_id)
        except Exception as e:
            self.logger.error(f"Error in after_conversation_end: {e}")
        

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
    Cleans all short memories older than clean_after_days days
    '''
    @hookimpl 
    # async def rag_loaded(self):
    async def user_idle_on_pc(self):
        self.logger.info("User idle,cleaning short memory")
        clean_after_days = self.settings.get("clean_after_days", 14)
        try:
            clean_after_days = int(clean_after_days)  # Ensure it's an integer
        except (TypeError, ValueError):
            self.logger.warning(f"Invalid clean_after_days value: {clean_after_days}, using default")
            
            
        result = await self.pm.trigger_hook(
            hook_name="clean_short_term_memory", 
            clean_after_days=clean_after_days
        )
        
        return True

    ''' 
    Returns TRUE if memory does not exist in RAG, otherwise FALSE 
    def check_memory(memory):
        Calls LLM to double check memory before inserting into RAG    
    '''
    async def memory_review(self, conversation, memory):
        """Reviews a memory to determine if it should be stored"""
        start_time = time.time()
        
        try:
            # Get RAG context
            rag = await self.query_rag_async(memory.fact)
            # self.logger.info(f"RAG context received: {rag}")
            
            # Convert Pydantic Fact object to dict
            memory_dict = {
                "fact": memory.fact,
                "type": memory.type
            }
            
            # Create the memory review package
            memory_to_be_checked = {
                "conversation": conversation,
                "memory": memory_dict,
                "rag": rag
            }
            
            # Set up prompts
            sys_pm = PromptManager(template=MEMORY_REVIEW_SYSTEM_PROMPT)
            system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
            
            pm = PromptManager(template=MEMORY_REVIEW_PROMPT_TEMPLATE)
            prompt = pm.create_prompt(memory_to_be_checked=json.dumps(memory_to_be_checked))

            # Call LLM with ValidationResponse schema
            llm = LLMManager(
                self.settings.get("provider"), 
                self.settings.get("api_key"), 
                self.settings.get("model_name")
            )
            llm.set_json_schema(ValidationResponse)
            validation = llm.invoke(system_prompt, prompt)
            
            has_error, validation = self.handle_llm_error(validation)
            if has_error:
                self.logger.error(f"Error in LLM validation: {validation}")
                return ValidationResponse(valid=False, reason="Error in memory validation")
            
            end_time = time.time()
            self.logger.info(f"Memory review completed in {end_time - start_time} seconds. Result: {validation}")
            return validation
            
        except Exception as e:
            self.logger.error(f"Error in memory_review: {e}")
            return ValidationResponse(valid=False, reason=f"Error during memory review: {str(e)}")
    
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        """Query RAG for existing INGESTED/LONG term memories, filtering out short-term memories"""
        try:
            # Specify store types to only query ingested and long-term memories
            store_types = [0, 1]  # INGESTED=0, LONG_TERM=1
            self.logger.info(f"Querying RAG with text: {msg}, store_types: {store_types}")
            
            chunk_ids=await self.pm.trigger_hook(
                hook_name="query_rag", 
                query_text=msg,
                store_types=store_types,
                return_chunk_ids=True
            )
            self.logger.info(f"Chunk IDs: {chunk_ids}") 
            filtered_results = await self.pm.trigger_hook(
                hook_name="filter_by_timeframe", 
                preflow_dict={},
                docstore_ids_by_type=chunk_ids
            )
            self.logger.info(f"FILTERED RESULTS: {filtered_results}")
            actual_filtered_results = normalize_filter_by_timeframe_result(filtered_results)
            
            return "---" + '\n'.join(actual_filtered_results.get(0, [])) + '\n' + '\n'.join(actual_filtered_results.get(1, [])) 
        except Exception as e:
            self.logger.error(f"Error in query_rag_async: {e}")
            return "---"  # Return empty context in case of error
        
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