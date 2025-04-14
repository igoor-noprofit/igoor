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
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

PROMPT_TEMPLATE = """
La personne affectée par la maladie s'appelle {bio_name}. Considère son état actuel pour éviter des prédictions incompatibles avec ses capacités physiques:

{health_state}

---
Pour répondre tu peux utiliser le contexte statique extrait des documents sur la vie de {bio_name}:

{static_context}

---
Tu peux utiliser aussi les informations de la mémoire à long terme,ordonnées par date croissante:

{long_term}

---

Tu peux utiliser aussi les informations de la mémoire à court terme,ordonnées par date croissante:

{short_term}

--- 
Si besoin utilises aussi les infos du contexte dynamique suivant:

{dynamic_context}

---
Prends en considération le style expressif de {bio_name}:

{bio_style}

Propose des réponses influencés par le style dans la mesure de: {bio_style_weight}.

---
Réponds en utilisant aussi les contextes ci-dessus à la dernière question de cette conversation: {conversation}
"""

class Flow(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=AssistantPrompts("locales/","fr_FR")
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.bio_style=bio.get("style")
        self.bio_style_weight=bio.get("style_weight")
        self.health_state=bio.get("health_state")
        self.is_loaded = True
    
    @hookimpl
    def startup(self):
        print("FLOW STARTUP")
    
    @hookimpl
    def gui_ready(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # Schedule the coroutine to be run
        asyncio.create_task(self._startup_async())
        
    @hookimpl
    def abandon_conversation(self,cause="user_abandoned"):
        self.send_message_to_frontend({"action":"clear_answers"})
        
    async def _startup_async(self):
        print("sending status ready")
        await self.send_status("ready")

    def process_incoming_message(self, message):
        try:
            print("Received msg: " + message)
            # Attempt to parse the message as JSON
            message_dict = json.loads(message)
            # Output the JSON variables and values
            for key, value in message_dict.items():
                print(f"Key: {key}, Value: {value}")
            # Ensure message_dict is a dictionary
            if isinstance(message_dict, dict):
                action = message_dict.get("action")
                if  action == "speak":
                    msg = message_dict.get("msg", "")
                    # Trigger hook in plugin manager with msg
                    asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                    asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master"))
                elif action == "abandon_conversation":
                    asyncio.create_task(self.pm.trigger_hook(hook_name="abandon_conversation", cause="user_abandoned"))
                else:
                    print("Unrecognized action in incoming message.")
                    
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
        
    '''
    Receives msg from speaker
    Asks LLM for topic and timeframe to search in memory
    Queries RAG with timeframe
    Filters RAG results by timeframe
    Sends RAG results to LLM query
    '''
    @hookimpl
    async def asr_msg(self, msg: str) -> None:
        start_time = time.time()
        dynamic_context = self.get_dynamic_context().copy()
        # Remove the conversation attribute from dynamic context
        conversation = dynamic_context.get("conversation")
        
        # PREFLOW HERE
        preflow_dict = await self.preflow(conversation)
        
        asyncio.create_task(self.pm.trigger_hook(hook_name="set_conversation_topic",topic=preflow_dict.get("theme")))
        # Initialize context
        context = ""
        
        if not preflow_dict:
            # If preflow fails, query all store types
            context = self.pm.trigger_hook(
                hook_name="query_rag", 
                query_text=conversation, 
                store_types=[0,1,2], 
                return_chunk_ids=False
            )
        else:
            # Determine which store types to query based on m_type
            store_types = []
            
            if "short" in preflow_dict.get("m_type", []):
                # SHORT_TERM = 2
                store_types.append(2)  # Add SHORT_TERM
            
            if "long" in preflow_dict.get("m_type", []):
                # LONG_TERM = 1, INGESTED = 0
                store_types.extend([0, 1])  # Add INGESTED and LONG_TERM
            
            # If no specific memory types, query all
            if not store_types:
                self.logger.warning("No specific memory types found in preflow_dict, querying all store types.")
                store_types = [0, 1, 2]  # Query all store types
            
            self.logger.info(f"SEARCH MEMORY types according to preflow: {store_types}")  # Log the store types being queried    
                
            # Make a single call to query_rag_async with all needed store types
            chunk_ids = await self.pm.trigger_hook(
                hook_name="query_rag", 
                # query_text=preflow_dict.get("theme"),
                query_text=conversation, 
                store_types=store_types, 
                return_chunk_ids=True
            )
            self.logger.info(f"Chunk IDs: {chunk_ids}") 
            filtered_results = await self.pm.trigger_hook(
                hook_name="filter_by_timeframe", 
                preflow_dict=preflow_dict,
                docstore_ids_by_type=chunk_ids
            )
            self.logger.info(f"FILTERED RESULTS: {filtered_results}")
            # Reorder RAG based on chunk_ids
        # Continue with the rest of your function
        del dynamic_context["conversation"]
        assistant_type = "flow"
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        pm = PromptManager(template=PROMPT_TEMPLATE)
        
        # Pass the context to the prompt
        prompt = pm.create_prompt(
            bio_name=self.bio_name,
            bio_style=self.bio_style,
            bio_style_weight=self.bio_style_weight,
            health_state=self.health_state,
            static_context=context,
            long_term="",  # Not separating by memory type in this approach
            short_term="", 
            dynamic_context=dynamic_context, 
            conversation=conversation,
            log_folder=self.plugin_folder
        )       
        
        print(f"FINAL PROMPT : {prompt}")
        try:
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
            llm.set_json_schema(Answers)
            answers = llm.invoke(system_prompt,prompt)
            has_error, answers = self.handle_llm_error(answers)
            if has_error:
                return answers
                
            answers_dict = answers.dict()
            if answers_dict.get("answers"):
                self.send_message_to_frontend(answers.json()) 
            else:
                print("NO ANSWERS RECEIVED")
                self.send_error_to_frontend("llm_error")
            end_time = time.time()
            print(f"Time taken for processing: {end_time - start_time} seconds")
        except Exception as e:
            print(f"Unexpected error in asr_msg: {str(e)}")
            self.send_error_to_frontend("llm_error",e)
        
    async def reorder_rag(self, chunk_ids:dict,preflow_dict:dict):
        """Reorders the RAG context based on the given chunk IDs.
            For each store type in chunk_ids, retrieves the chunks based on the given IDs from the sqlite db,
            along with their timestamps. Then uses preflow_dict to filter the chunks based on their timestamps and sort them             
            from the oldest to the newest.
            Args:
                chunk_ids (dict): A dictionary where the keys are store types (0, 1, or 2) and the values are lists of chunk IDs.
                preflow_dict (dict): A dictionary containing the preflow result.
        """
        for store_type, ids in chunk_ids.items():
            # Retrieve chunks from sqlite db based on chunk_ids
            chunks = await self.pm.trigger_hook(hook_name="get_chunks_by_ids", chunk_ids=ids, store_type=store_type)
            # Filter chunks based on timestamps
        return False
        
    async def preflow(self,conversation:str) -> dict:
        start_time = time.time()
        """Performs a first LLM call to create or update conversation topic and to know WHICH memory to search"""
        assistant_type = "preflow"
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        pm = PromptManager(template="{conversation}")
        prompt = pm.create_prompt(conversation=conversation)       
        print(f"FINAL PROMPT : {prompt}")
        try:
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
            llm.set_json_schema(ConversationModel)
            preflow = llm.invoke(system_prompt,prompt)
            has_error, preflow = self.handle_llm_error(preflow)
            if has_error:
                return preflow
                
            preflow_dict = preflow.dict()
            if preflow_dict.get("theme"):
                return preflow_dict
            else:
                return False
            end_time = time.time()
            print(f"PREFLOW time taken for processing: {end_time - start_time} seconds")
        except Exception as e:
            print(f"Unexpected error in preflow: {str(e)}")
            self.send_error_to_frontend("llm_error",e)
        return False
        
    def get_dynamic_context(self):
        return context_manager.get_context()
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
        
    
    def test_queries(self) -> None:
        queries = [
            "Q: Qu'est-ce que t'as mangé hier ?",   
        ]
        for query in queries:
            asyncio.run(self.asr_msg(query))
        

class Answers(BaseModel):
    answers: List[str]

class TimeframeType(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"

class Period(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    FULL_DAY = "full_day"

class MType(str, Enum):
    SHORT = "short"
    LONG = "long"

class Category(str, Enum):
    BIO = "bio"
    DAILY = "daily"

class Timeframe(BaseModel):
    type: TimeframeType = Field(description="absolute for specific dates, relative for references like 'yesterday'")
    reference: str = Field(description="the original time reference from the query")
    start_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format, optional for absolute dates")
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format, optional for absolute dates")
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format, optional")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format, optional")
    relative_days: Optional[int] = Field(None, description="days relative to current date (e.g., -1 for yesterday)")
    period: Optional[Period] = Field(None, description="optional period of the day")

class ConversationModel(BaseModel):
    theme: str = Field(description="the subject of the conversation")
    m_type: List[MType] = Field(description="short or long or both")
    cat: List[Category] = Field(description="bio or daily or both")
    timeframe: Timeframe