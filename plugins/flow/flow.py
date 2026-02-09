from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from settings_manager import SettingsManager
from llm_manager import LLMManager
import asyncio,json,time
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union, Dict
from enum import Enum
from datetime import datetime
from utils import normalize_filter_by_timeframe_result

class Flow(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=self.get_my_prompts()
        self.global_settings = SettingsManager()
        self.global_settings_updated()
        self.is_loaded = True
    
    @hookimpl 
    def global_settings_updated(self):
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.bio_style=bio.get("style")
        self.bio_style_weight=bio.get("style_weight")
        self.health_state=bio.get("health_state")
    
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
    def abandon_conversation(self,cause="abandoned"):
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
                    asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master", msg_input="flow"))
                elif action == "abandon_conversation":
                    asyncio.create_task(self.pm.trigger_hook(hook_name="abandon_conversation", cause="abandoned"))
                elif action == "get_settings":
                    self.send_settings_to_frontend()
                else:
                    # Dump the raw message and the parsed dictionary to help debugging unknown actions
                    try:
                        self.logger.error(f"FLOW: Unrecognized action in incoming message. Raw message: {message}")
                        self.logger.error(f"FLOW: Parsed message dict: {message_dict}")
                    except Exception:
                        # Fallback if logger formatting fails for any reason
                        print("FLOW: Unrecognized action in incoming message.")
                        print("Raw message:", message)
                        print("Parsed dict:", message_dict)
                    
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
            # self.logger.info(f"Chunk IDs: {chunk_ids}") 
            filtered_results = await self.pm.trigger_hook(
                hook_name="filter_by_timeframe", 
                preflow_dict=preflow_dict,
                docstore_ids_by_type=chunk_ids
            )
            # self.logger.info(f"FILTERED RESULTS: {filtered_results}")
            actual_filtered_results = normalize_filter_by_timeframe_result(filtered_results)

        # Continue with the rest of your function
        del dynamic_context["conversation"]
        system_prompt = self.prompts.get("flow", {}).get("system")
        pm = PromptManager(template=self.prompts.get("flow", {}).get("usr"))
        
        # Pass the context to the prompt
        prompt = pm.create_prompt(
            bio_name=self.bio_name,
            bio_style=self.bio_style,
            bio_style_weight=self.bio_style_weight,
            health_state=self.health_state,
            static_context='\n'.join(actual_filtered_results.get(0, [])), # Use actual_filtered_results
            long_term='\n'.join(actual_filtered_results.get(1, [])),  # Use actual_filtered_results
            short_term='\n'.join(actual_filtered_results.get(2, [])), # Use actual_filtered_results
            dynamic_context=dynamic_context, 
            conversation=conversation,
            log_folder=self.plugin_folder
        )
        
        print(f"FINAL PROMPT : {prompt}")
        try:
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"), temperature=self.settings.get("temperature",1))
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
        
    '''
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
    '''
        
    async def preflow(self,conversation:str) -> dict:
        start_time = time.time()
        """Performs a first LLM call to create or update conversation topic and to know WHICH memory to search"""
        system_prompt = self.prompts.get("preflow", {}).get("system")
        pm = PromptManager(template="Jour et heure actuelle: {datetime} Conversation : {conversation}")
        now = datetime.now()
        formatted_datetime = now.strftime("%A %d %B %Y %H:%M")  # e.g., "Monday 22 April 2025"
        prompt = pm.create_prompt(datetime=formatted_datetime, conversation=conversation)       
        print(f"FINAL PROMPT : {prompt}")
        try:
            model_name = self.settings.get("preflow_model_name") or self.settings.get("model_name")
            model_temperature = self.settings.get("preflow_temperature") or self.settings.get("temperature",0.5)
            llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), model_name, temperature=model_temperature)
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
    answers: Dict[str, List[str]]

class TimeframeType(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"

class Period(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    FULL_DAY = "full_day"
    FULL_PERIOD = "full_period"

class MType(str, Enum):
    SHORT = "short"
    LONG = "long"

class Timeframe(BaseModel):
    type: TimeframeType = Field(description="absolute for specific dates, relative for references like 'yesterday'")
    reference: str = Field(description="the original time reference from the query")
    start_date: str = Field(pattern=r"^$|^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format or empty")
    end_date: str = Field(pattern=r"^$|^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format or empty")
    relative_days: int = Field(description="days relative to current date (e.g., -1 for yesterday)")
    period: Period = Field(description="period of the day")

class ConversationModel(BaseModel):
    theme: str = Field(description="the subject of the conversation")
    m_type: List[MType] = Field(description="short or long or both")
    timeframe: Timeframe = Field(description="timeframe for the query")