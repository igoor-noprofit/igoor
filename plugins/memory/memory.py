from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from settings_manager import SettingsManager
from llm_manager import LLMManager
import asyncio,json,time
from langchain_core.messages.ai import AIMessage
from pydantic import BaseModel
from typing import List
from utils import normalize_filter_by_timeframe_result

class Memory(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.global_settings = SettingsManager()
        self.prompts=self.get_my_prompts()
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.is_loaded = True
        
    
    @hookimpl
    def startup(self):
        loop = asyncio.get_event_loop()
        try:
            loop = asyncio.get_event_loop()
            self.mark_ready()
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
        # start_time = time.time()
        
        # Get conversation ID if available and log it
        conversation_id = last_conversation.get("thread_id")
        
        if conversation_id is None:
            self.logger.warning("No conversation_id found in last_conversation")
            self.logger.debug(f"last_conversation contents: {last_conversation}")
        else:
            self.logger.info(f"Processing conversation end with ID: {conversation_id}")

        # SYSTEM PROMPT
        template=self.prompts.get("memory", {}).get("system")
        sys_pm = PromptManager(template)
        system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
        print(f"Memory system prompt: {system_prompt}")
        
        # HUMAN PROMPT
        conversation = last_conversation.get("txt")
        print(f"Conversation text: {conversation}")
        pm = PromptManager(template=self.prompts.get("memory", {}).get("usr"))
        prompt = pm.create_prompt(conversation=conversation)       

        try:
            # Get memories from first LLM call
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
            llm.set_json_schema(DataModel)
            memories = llm.invoke(system_prompt, prompt)
            has_error, memories = self.handle_llm_error(memories)
            if has_error:
                self.logger.error(f"Error getting memories: {memories}")
                return memories

            # Set conversation topic from memory analysis
            if conversation_id is not None and hasattr(memories, 'theme') and memories.theme:
                self.logger.info(f"Updating conversation {conversation_id} topic from memory: {memories.theme}")
                await self.pm.trigger_hook(
                    hook_name="update_conversation_topic",
                    topic=memories.theme,
                    conversation_id=conversation_id
                )

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
            sys_pm = PromptManager(template=self.prompts.get("memory_review", {}).get("system"))
            system_prompt = sys_pm.create_prompt(bio_name=self.bio_name)
            
            pm = PromptManager(template=self.prompts.get("memory_review", {}).get("usr"))
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
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    fact: str
    type: str

class DataModel(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    theme: str
    tags: List[str]
    facts: List[Fact]

# MEMORY REVIEWER TEMPLATE
class ValidationResponse(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    valid: bool
    reason: str