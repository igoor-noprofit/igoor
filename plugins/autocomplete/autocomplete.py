from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from settings_manager import SettingsManager
from llm_manager import LLMManager
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio,json,time,re,unicodedata
import numpy as np
from utils import normalize_filter_by_timeframe_result


def _fold(s):
    """Case- and accent-insensitive form of s (e.g. 'Être' -> 'etre', 'école' -> 'ecole').
    Used so word predictions match regardless of case or accents — something SQLite
    LIKE / COLLATE NOCASE cannot do for non-ASCII (French) characters."""
    if not s:
        return ""
    decomposed = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_accents.lower()


class ShortPredictionsRequest(BaseModel):
    input: str

class ShortPredictionsResponse(BaseModel):
    predictions: List[str]

class Autocomplete(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=self.get_my_prompts()
        self.global_settings = SettingsManager()
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.bio_style=bio.get("style")
        self.health_state=self.global_settings.get_health_state()
        self.is_loaded = True
        self.only_exact_matches = self.settings.get("only_exact_matches", False)
        self.allow_virtual_keyboard = self.settings.get("allow_virtual_keyboard", False)
        self.short_prediction_words = self.settings.get("short_prediction_words", 1)
        # Live input synced from the frontend (see the "typing" action) so that
        # phrase (LLM) predictions can be dropped when the user types past them.
        self._current_input = ""
        self.router = None
        self._build_prompt_templates()
        print(f"ONLY EXACT MATCHES: {self.only_exact_matches}")
    
    def _build_prompt_templates(self):
        """Pre-build PromptManagers with static vars filled in."""
        reply_language = self.global_settings.get_reply_language()
        
        # Pre-fill system prompt (contains {reply_language})
        sys_template = self.prompts.get("autocomplete", {}).get("system", "")
        self._auto_system_prompt = sys_template.replace("{reply_language}", reply_language)
        
        # Pre-fill user prompt template with static vars
        self._auto_usr_pm = PromptManager(template=self.prompts.get("autocomplete", {}).get("usr"))
        self._auto_usr_pm.partial(
            bio_name=self.bio_name,
            reply_language=reply_language,
            bio_style=self.bio_style,
            health_state=self.health_state,
            bio_context=self.get_bio_context(),
        )
    
    @hookimpl
    def global_settings_updated(self):
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.bio_style = bio.get("style")
        self.health_state = self.global_settings.get_health_state()
        self._build_prompt_templates()
    
    @hookimpl
    def bio_context_updated(self):
        """Reload prompt templates when biorecorder bio.md has been created or updated."""
        self.logger.info("Autocomplete: bio_context_updated — rebuilding prompt templates")
        self._build_prompt_templates()

    @hookimpl
    def warmup(self):
        """Boot warmup: pre-warm the LLM client/cache with the real autocomplete prompt.
        Sends the full filled user prompt (static fields filled, dynamic fields blanked)
        so the largest stable prefix is cached."""
        if not (getattr(self, "_auto_system_prompt", None) and getattr(self, "_auto_usr_pm", None)):
            return
        try:
            user_prompt = self._auto_usr_pm.create_prompt(
                static_context="", long_term="", short_term="",
                dynamic_context={}, conversation="", successful_predictions="",
                past_conversations_msgs="", input="", last_conversations=""
            )
            self._warmup_llm(self._auto_system_prompt, user_prompt=user_prompt)
        except Exception as e:
            self.logger.warning(f"Autocomplete warmup render failed, falling back to system-only: {e}")
            self._warmup_llm(self._auto_system_prompt)
    
    @hookimpl
    def startup(self):
        print("AUTOCOMPLETE STARTUP")
        self.debug_db_status()
        self._ensure_router()
        if hasattr(self, 'pm') and hasattr(self.pm, 'fastapi_app'):
            self.pm.fastapi_app.include_router(self.router)
        self.mark_ready()
    
    def _ensure_router(self):
        """Initialize FastAPI router with endpoints"""
        if self.router is not None:
            return
        
        self.router = APIRouter(prefix="/api/plugins/autocomplete", tags=["autocomplete"])
        
        @self.router.post("/short-predictions", response_model=ShortPredictionsResponse)
        async def get_short_predictions_endpoint(request: ShortPredictionsRequest):
            """Get short (2-word) predictions for inline autocomplete"""
            return await self.get_short_predictions(request.input)
        
    @hookimpl
    def abandon_conversation(self):
        self.clear_input()
        
    @hookimpl
    def restart_asr(self):
        self.clear_input()
    
    @hookimpl
    def speak(self, message):
        """Clear autocomplete input when a phrase is spoken"""
        self.clear_input()
        
    def clear_input(self):
        self.send_message_to_frontend({"action":"clear"})
        
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
                if action == "speak":
                    msg = message_dict.get("msg")
                    print (f"Speaking {msg}")
                    if msg:
                        asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg, skip_asr=False))
                        asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master", msg_input="auto"))
                    else:
                        print("Speak action is present but msg is empty.")
                elif action == "backToDaily":
                    asyncio.create_task(self.send_switch_view_to_app("daily"))
                elif action == "prediction_selected":
                    # Store successful prediction in database
                    input_text = message_dict.get("input")
                    completion = message_dict.get("completion")
                    if input_text and completion:
                        asyncio.create_task(self.store_successful_prediction(input_text, completion))
                elif action == "typing":
                    # Live input sync from the frontend. Lets predict() detect
                    # staleness: a phrase (LLM) result is dropped if the user has
                    # typed past the input it was generated for.
                    self._current_input = message_dict.get("input", "")
                elif message_dict.get("msg"):
                    asyncio.create_task(self.pm.trigger_hook(hook_name="reset_conversation_timeout"))
                    input_value = message_dict.get("msg")
                    if input_value:
                        asyncio.create_task(self.send_switch_view_to_app("autocomplete"))
                        asyncio.create_task(self.predict(input_value))
                    else:
                        print("Input key is present but empty.")
            else:
                print("Message is not a valid dictionary.")
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
    
    async def store_successful_prediction(self, input_text: str, completion: str):
        """Store a successful prediction in the database or update its hit count"""
        try:
            self.logger.info(f"Attempting to store prediction: {input_text} -> {completion}")
            # Check if database is initialized
            if self.db is None:
                self.logger.error("Database not initialized. Cannot store prediction.")
                return
                
            # Check if this prediction already exists
            self.logger.info("Checking if prediction exists...")
            result = await self.db_execute(
                "SELECT id, hits FROM predictions WHERE input = ? COLLATE NOCASE AND completion = ? COLLATE NOCASE",
                (input_text, completion)
            )
            
            self.logger.info(f"Query result: {result}")
            
            if result and len(result) > 0:
                # Update existing prediction hit count
                prediction_id = result[0]['id']
                hits = result[0]['hits'] + 1
                self.logger.info(f"Updating existing prediction (ID: {prediction_id}) with hits: {hits}")
                
                # The issue might be here - let's fix the UPDATE statement
                await self.db_execute(
                    "UPDATE predictions SET hits = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (hits, prediction_id)
                )
                
                # Let's verify the update worked
                verify_result = await self.db_execute(
                    "SELECT hits FROM predictions WHERE id = ?", 
                    (prediction_id,)
                )
                
                if verify_result and len(verify_result) > 0:
                    self.logger.info(f"Verified update: new hit count is {verify_result[0]['hits']}")
                else:
                    self.logger.error(f"Failed to verify update for prediction ID {prediction_id}")
                    
                self.logger.info(f"Updated prediction hit count: {input_text} -> {completion} (hits: {hits})")
            else:
                # Insert new prediction
                self.logger.info("Inserting new prediction...")
                insert_result = await self.db_execute(
                    "INSERT INTO predictions (input, completion, hits) VALUES (?, ?, 1)",
                    (input_text, completion)
                )
                self.logger.info(f"Insert result: {insert_result}")
                self.logger.info(f"Stored new prediction: {input_text} -> {completion}")
        except Exception as e:
            self.logger.error(f"Error storing prediction: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def get_top_predictions(self, input_text: str, limit: int = 3):
        """Get top predictions for an input text based on hit frequency"""
        try:
            # Get exact matches first (case-insensitive; COLLATE NOCASE is ASCII-only,
            # so accented capitals are matched via _fold in the short-prediction path)
            result = await self.db_execute(
                "SELECT input, completion, hits FROM predictions WHERE input = ? COLLATE NOCASE ORDER BY hits DESC LIMIT ?",
                (input_text, limit)
            )
            
            if not self.only_exact_matches:
                # If we don't have enough exact matches, try partial matches
                if not result or len(result) < limit:
                    remaining = limit - (len(result) if result else 0)
                    partial_results = await self.db_execute(
                        "SELECT input, completion, hits FROM predictions WHERE input LIKE ? ORDER BY hits DESC LIMIT ?",
                        (f"{input_text}%", remaining)
                    )
                    
                    if result and partial_results:
                        result.extend(partial_results)
                    elif partial_results:
                        result = partial_results
            
            return result if result else []
        except Exception as e:
            self.logger.error(f"Error getting top predictions: {e}")
            return []
    
    async def get_short_predictions(self, input_text: str) -> ShortPredictionsResponse:
        """
        Get short (2-word) predictions for inline autocomplete.
        Searches predictions table and conversation messages.
        Returns predictions with the already-typed portion removed.
        """
        predictions = {}  # Use dict to track hits for ordering: {prediction: hits}
        
        if not input_text or len(input_text.strip()) < 2:
            return ShortPredictionsResponse(predictions=[])
        
        input_lower = input_text.lower().strip()
        folded_input = _fold(input_text)

        try:
            # 1. Search predictions table. Rows are fetched and matched in Python with
            # _fold() so matching is case- AND accent-insensitive — SQLite LIKE only
            # handles ASCII case, which is inadequate for French (e.g. 'etre' should
            # match 'être'). The predictions table is user-bounded, so a scan per
            # keystroke is cheap.
            if self.db:
                pred_results = await self.db_execute(
                    "SELECT input, completion, hits FROM predictions ORDER BY hits DESC LIMIT 2000"
                )

                if pred_results:
                    for row in pred_results:
                        completion = row.get('completion', '')
                        hits = row.get('hits', 0)
                        # case/accent-insensitive containment on input or completion
                        if folded_input in _fold(row.get('input', '')) or folded_input in _fold(completion):
                            # Extract short prediction from completion
                            short_pred = self._extract_short_prediction(input_text, completion, self.short_prediction_words)
                            if short_pred:
                                # Keep the one with highest hits
                                if short_pred not in predictions or predictions[short_pred] < hits:
                                    predictions[short_pred] = hits
            
            # 2. Search conversation messages via hook
            conversation_msgs_result = await self.pm.trigger_hook(
                hook_name="get_conversation_msgs_containing",
                query_text=input_lower
            )
            
            if conversation_msgs_result:
                # trigger_hook returns a list of results; extract the actual content
                conversation_msgs = None
                if isinstance(conversation_msgs_result, list) and len(conversation_msgs_result) > 0:
                    conversation_msgs = conversation_msgs_result[0]
                elif isinstance(conversation_msgs_result, str):
                    conversation_msgs = conversation_msgs_result
                
                if conversation_msgs:
                    # Ensure we have a string before splitting
                    if isinstance(conversation_msgs, list):
                        # Handle if it's still a list - join or skip
                        conversation_msgs = '\n'.join(str(m) for m in conversation_msgs if m)
                    
                    if isinstance(conversation_msgs, str) and conversation_msgs:
                        # Parse messages (format: "datetime\tmessage" per line)
                        for msg_line in conversation_msgs.split('\n'):
                            if '\t' in msg_line:
                                parts = msg_line.split('\t', 1)
                                if len(parts) > 1:
                                    msg_text = parts[1]
                                    short_pred = self._extract_short_prediction(input_text, msg_text, self.short_prediction_words)
                                    if short_pred and short_pred not in predictions:
                                        predictions[short_pred] = 0  # Lower priority for conversation matches
            
        except Exception as e:
            self.logger.error(f"Error getting short predictions: {e}")
        
        # Sort by hits DESC and return top 2
        sorted_predictions = sorted(predictions.keys(), key=lambda p: predictions[p], reverse=True)
        return ShortPredictionsResponse(predictions=sorted_predictions[:2])
    
    def _extract_short_prediction(self, input_text: str, full_text: str, word_count: int = 3) -> Optional[str]:
        """
        Extract the continuation of input_text from full_text.
        Returns the next N words (excluding the already-typed portion).
        Preserves leading space if present in the original text.
        """
        if not full_text or not input_text:
            return None
        
        input_folded = _fold(input_text).strip()
        full_folded = _fold(full_text).strip()

        # Find where the input matches in the full text (case/accent-insensitive)
        idx = full_folded.find(input_folded)
        if idx == -1:
            return None

        # Get the portion after the input (preserve leading space if present).
        # _fold preserves length for French text, so the index aligns with the
        # original string and we can slice it directly (keeping real casing).
        continuation = full_text[idx + len(input_text):]
        
        if not continuation or not continuation.strip():
            return None
        
        # Check if there was a leading space
        has_leading_space = continuation.startswith(' ')
        continuation = continuation.strip()
        
        # Extract first N words
        words = continuation.split()[:word_count]
        if not words:
            return None
        
        result = ' '.join(words)
        
        # Only return if it starts with a letter (avoid punctuation at start)
        if result and result[0].isalpha():
            # Prepend space if original had one
            if has_leading_space:
                result = ' ' + result
            return result
        
        return None
    
    async def format_successful_predictions(self, input_text: str):
        """Format top predictions for inclusion in the prompt"""
        predictions = await self.get_top_predictions(input_text)
        
        if not predictions:
            return "[]"  # Return empty JSON array if no predictions
        
        # Format as a simple list of completions with hit counts
        formatted_completions = []
        for pred in predictions:
            formatted_completions.append({
                "text": pred['completion'],
                "hits": pred['hits']
            })
        
        # Convert to JSON string for clean representation in the prompt
        return json.dumps(formatted_completions, ensure_ascii=False, indent=2)
    
    async def predict(self, msg: str) -> None:
        start_time = time.time()
        print("AUTOCOMPLETE PREDICTIONS")
        dynamic_context = self.get_dynamic_context()
        print(f"DYNAMIC CONTEXT IS {dynamic_context}")
        conversation = dynamic_context.get("conversation")
        # print(f"CONVERSATION IS : {conversation}")
        # Make a single call to query_rag_async with all needed store types
        
        chunk_ids = await self.pm.trigger_hook(
            hook_name="query_rag", 
            # query_text=preflow_dict.get("theme"),
            query_text=conversation if conversation else msg, # we give entire conversation to the RAG if possible, to expand the context
            store_types=[0,1,2], 
            return_chunk_ids=True
        )
        filtered_results = await self.pm.trigger_hook(
            hook_name="filter_by_timeframe", 
            preflow_dict={},
            docstore_ids_by_type=chunk_ids
        )
        actual_filtered_results = normalize_filter_by_timeframe_result(filtered_results)
        self.logger.info(f"FILTERED RESULTS: {filtered_results}")
        # Get successful predictions for this input
        successful_predictions = await self.format_successful_predictions(msg)
        past_conversations_msgs = await self.pm.trigger_hook(
            hook_name="get_conversation_msgs_containing",
            query_text=msg
        )
        
        # Get last conversations for additional context
        last_conversations_result = await self.pm.trigger_hook(hook_name="get_last_conversations")
        last_conversations = last_conversations_result[0] if last_conversations_result and last_conversations_result[0] else ""

        # Per-speaker history injection: past conversations with the current speaker.
        speaker_conversations = ""
        try:
            spk = next((r for r in (await self.pm.trigger_hook(hook_name="get_context_speaker") or []) if r and r.get("speakers_id")), None)
            if spk:
                speaker_conversations = next((r for r in (await self.pm.trigger_hook(hook_name="get_speaker_conversations", speakers_id=spk["speakers_id"]) or []) if r), "")
        except Exception as e:
            self.logger.warning(f"speaker_conversations lookup failed: {e}")

        system_prompt = self._auto_system_prompt
        # Only pass dynamic vars (static ones are pre-filled via partial)
        prompt = self._auto_usr_pm.create_prompt(
            static_context='\n'.join(actual_filtered_results.get(0, [])),
            long_term='\n'.join(actual_filtered_results.get(1, [])),
            short_term='\n'.join(actual_filtered_results.get(2, [])),
            dynamic_context=dynamic_context,
            conversation=conversation,
            successful_predictions=successful_predictions,
            past_conversations_msgs=past_conversations_msgs,
            input=msg,
            last_conversations=last_conversations,
            speaker_conversations=speaker_conversations
        )       
        print(f"FINAL HUMAN PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
        llm.set_json_schema(Answers)
        answers = llm.invoke(system_prompt,prompt, reasoning_effort=self.settings.get("reasoning_effort"))
        print(f"TYPE = {type(answers)}, ANSWERS: {answers}")
        answers_dict = answers.dict()
        # Staleness guard: drop this phrase prediction if the user has typed
        # past the input it was generated for. Without this, a slow LLM result
        # for an earlier input can render after (and visually leapfrog) the more
        # recent inline word predictions.
        if (self._current_input or "").strip() != msg.strip():
            self.logger.info(
                f"Dropping stale phrase prediction for '{msg}' "
                f"(current input: '{self._current_input}')"
            )
            return
        if answers_dict.get("answers"):
            # Include the original input with the answers
            response = {
                "input": msg,
                "completions": answers_dict.get("answers")
            }
            self.send_message_to_frontend(json.dumps(response), "flow") 
        else:
            print("NO PREDICTIONS RECEIVED")
        end_time = time.time()
        print(f"Time taken for processing: {end_time - start_time} seconds")
        
    def get_dynamic_context(self):
        return context_manager.get_context()
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
        
    @hookimpl
    async def store_autocomplete_prediction(self, input_text: str, completion: str):
        """Implement the hook to store successful predictions"""
        self.logger.info(f"Hook called to store prediction: {input_text} -> {completion}")
        try:
            # Make sure to await the async function
            await self.store_successful_prediction(input_text, completion)
            self.logger.info(f"Successfully stored prediction in database: {input_text} -> {completion}")
        except Exception as e:
            self.logger.error(f"Error in store_autocomplete_prediction: {e}")

class Answers(BaseModel):
    model_config = {"extra": "forbid"}  # Required for Groq strict mode (adds additionalProperties: false)
    answers: List[str]