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
    
    def _build_prompt_templates(self):
        """Pre-build PromptManagers with static vars filled in (called at init and on settings change)."""
        reply_language = self.global_settings.get_reply_language()
        
        # Pre-fill system prompt for flow (contains {reply_language})
        sys_template = self.prompts.get("flow", {}).get("system", "")
        self._flow_system_prompt = sys_template.replace("{reply_language}", reply_language)
        
        # Pre-fill user prompt template with static vars
        self._flow_usr_pm = PromptManager(template=self.prompts.get("flow", {}).get("usr"))
        self._flow_usr_pm.partial(
            bio_name=self.bio_name,
            reply_language=reply_language,
            bio_style=self.bio_style,
            bio_style_weight=self.bio_style_weight,
            health_state=self.health_state,
        )
    
    @hookimpl 
    def global_settings_updated(self):
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.bio_style=bio.get("style")
        self.bio_style_weight=bio.get("style_weight")
        self.health_state=bio.get("health_state")
        self._build_prompt_templates()
    
    @hookimpl
    def startup(self):
        self.mark_ready()
    
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

        # SEMANTIC VAD GATE: Check if speaker has finished speaking
        always_generate = False
        asrjs_configs = await self.pm.trigger_hook(hook_name="get_asrjs_config")
        if asrjs_configs and asrjs_configs[0]:
            always_generate = asrjs_configs[0].get("always_generate", False)
        # Fall back to global onboarding settings for semantic model
        ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
        flow_semantic_model = self.settings.get("semantic_model_name")
        if flow_semantic_model:
            semantic_model = flow_semantic_model
        else:
            semantic_model = ai.get("semantic_model_name") or ai.get("model_name")
        
        if semantic_model and not always_generate:
            vad_result = await self.semantic_vad(conversation)
            if vad_result == "nok":
                print("Semantic VAD: Speaker has not finished speaking")
                self.send_message_to_frontend(json.dumps({
                    "action": "listening",
                    "status": "waiting_for_more"
                }))
                return
        
        # Check if preflow is enabled
        preflow_enabled = self.settings.get("preflow_enabled", False)
        
        if preflow_enabled:
            # PREFLOW HERE
            preflow_dict = await self.preflow(conversation)
            # Set conversation topic from preflow
            if preflow_dict and preflow_dict.get("theme"):
                asyncio.create_task(self.pm.trigger_hook(hook_name="set_conversation_topic",topic=preflow_dict.get("theme")))
        else:
            # PREFLOW DISABLED: Use defaults
            preflow_dict = {}
            # NOTE: Conversation topic will be set later by memory plugin's after_conversation_end
        
        # Determine store types
        if preflow_enabled and preflow_dict:
            # Determine which store types to query based on m_type from preflow
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
        else:
            # If preflow disabled or failed, query all store types
            store_types = [0, 1, 2]
                
        # Make a single call to query_rag_async with all needed store types
        chunk_ids = await self.pm.trigger_hook(
            hook_name="query_rag", 
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

        del dynamic_context["conversation"]
        
        # Get last conversations for additional context
        last_conversations_result = await self.pm.trigger_hook(hook_name="get_last_conversations")
        last_conversations = last_conversations_result[0] if last_conversations_result and last_conversations_result[0] else ""
        
        system_prompt = self._flow_system_prompt
        
        # Only pass dynamic vars (static ones are pre-filled via partial)
        prompt = self._flow_usr_pm.create_prompt(
            static_context='\n'.join(actual_filtered_results.get(0, [])),
            long_term='\n'.join(actual_filtered_results.get(1, [])),
            short_term='\n'.join(actual_filtered_results.get(2, [])),
            dynamic_context=dynamic_context, 
            conversation=conversation,
            last_conversations=last_conversations
        )
        
        print(f"FINAL PROMPT : {prompt}")
        try:
            # Fall back to global onboarding settings
            ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
            
            # Use global provider and api_key (flow settings are empty by default)
            provider = ai.get("provider")
            api_key = ai.get("api_key")
            
            # Use global model_name (flow settings are empty by default)
            model_name = ai.get("model_name")
            
            # Use global temperature (or default if not set)
            temperature = self.settings.get("temperature") if self.settings.get("temperature") is not None else ai.get("temperature", 1)
            
            llm = LLMManager(provider, api_key, model_name, temperature=temperature)
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
            # Fall back to global onboarding settings
            ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
            
            # Check model settings (preflow-specific first, then general)
            flow_preflow_model = self.settings.get("preflow_model_name")
            if flow_preflow_model:
                model_name = flow_preflow_model
            else:
                model_name = ai.get("model_name")
            
            # Check temperature settings (preflow-specific first, then general)
            flow_preflow_temp = self.settings.get("preflow_temperature")
            model_temperature = flow_preflow_temp if flow_preflow_temp is not None else ai.get("temperature", 0.5)
            
            # Use global provider and api_key
            provider = ai.get("provider")
            api_key = ai.get("api_key")
            
            llm = LLMManager(provider, api_key, model_name, temperature=model_temperature)
            llm.set_json_schema(ConversationModel)
            preflow = llm.invoke(system_prompt,prompt)
            has_error, preflow = self.handle_llm_error(preflow)
            if has_error:
                return preflow
                
            preflow_dict = preflow.dict()
            end_time = time.time()
            print(f"PREFLOW time taken for processing: {end_time - start_time} seconds")
            if preflow_dict.get("theme"):
                return preflow_dict
            else:
                return False
        except Exception as e:
            print(f"Unexpected error in preflow: {str(e)}")
            self.send_error_to_frontend("llm_error",e)
        return False
    
    async def semantic_vad(self, conversation: str) -> str:
        """Lightweight LLM call to check if speaker has finished talking. Returns 'ok' or 'nok'."""
        start_time = time.time()
        system_prompt = self.prompts.get("semantic_vad", {}).get("system")
        if not system_prompt:
            print("Semantic VAD: No prompt found, defaulting to 'ok'")
            return "ok"
        try:
            # Fall back to onboarding settings if flow settings are empty
            ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
            
            # Check if flow-specific semantic_model is set (rare override case)
            flow_semantic_model = self.settings.get("semantic_model_name")
            if flow_semantic_model:
                model_name = flow_semantic_model
            else:
                # Fallback to global onboarding settings
                # Check semantic_model_name first (for semantic VAD), then model_name (general)
                model_name = ai.get("semantic_model_name") or ai.get("model_name")
            provider = ai.get("provider")
            api_key = ai.get("api_key")
            
            # Validate provider and model_name before proceeding
            if not provider:
                print("Semantic VAD: No provider configured, defaulting to 'ok'")
                return "ok"
            if not model_name:
                print("Semantic VAD: No model configured, defaulting to 'ok'")
                return "ok"
            
            # Use LLMManager for all providers (including Groq) for observability
            print(f"Semantic VAD: Calling LLM with model '{model_name}' for conversation: {conversation[:100]}...")
            llm = LLMManager(provider, api_key, model_name, temperature=0)
            llm.set_json_schema(SemanticVADResponse)
            result = llm.invoke(system_prompt, f"Conversation:\n{conversation}")
            
            has_error, result = self.handle_llm_error(result)
            if has_error:
                print(f"Semantic VAD: LLM error, defaulting to 'ok'")
                return "ok"
            
            # Extract result from schema
            if isinstance(result, SemanticVADResponse):
                text = result.result.strip().lower()
            else:
                text = str(result).strip().lower()
            
            end_time = time.time()
            print(f"Semantic VAD result: '{text}' (took {end_time - start_time:.2f}s)")
            return "nok" if "nok" in text else "ok"
        except Exception as e:
            print(f"Semantic VAD error: {str(e)}, defaulting to 'ok'")
            return "ok"
        
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

class SemanticVADResponse(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    result: str = Field(description="'ok' if speaker has finished, 'nok' if still speaking")

class Answers(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
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
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    type: TimeframeType = Field(description="absolute for specific dates, relative for references like 'yesterday'")
    reference: str = Field(description="the original time reference from the query")
    start_date: str = Field(pattern=r"^$|^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format or empty")
    end_date: str = Field(pattern=r"^$|^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format or empty")
    relative_days: int = Field(description="days relative to current date (e.g., -1 for yesterday)")
    period: Period = Field(description="period of the day")

class ConversationModel(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode
    theme: str = Field(description="the subject of the conversation")
    m_type: List[MType] = Field(description="short or long or both")
    timeframe: Timeframe = Field(description="timeframe for the query")