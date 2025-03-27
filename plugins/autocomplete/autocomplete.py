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
from pydantic import BaseModel
from typing import List, Dict
import numpy as np

PROMPT_TEMPLATE = """
La personne affectée par la maladie s'appelle {bio_name}. Considère son état actuel pour éviter des prédictions incompatibles avec ses capacités physiques:

{health_state}

Utilise le contexte statique extrait des documents sur la vie de {bio_name}:

{static_context}

---
Utilise aussi les infos du contexte dynamique suivant :

{dynamic_context}
---

---
Prédictions précédentes:

{successful_predictions}
---

S'il y a une conversation en cours donne la priorité à la conversation en cours.
Prédis la suite de: {input}
"""

class Autocomplete(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        self.prompts=AssistantPrompts("locales/","fr_FR")
        self.global_settings = SettingsManager();
        self.settings = self.get_my_settings()
        bio = self.global_settings.get_bio()
        self.bio_name = bio.get("name")
        self.is_loaded = True
    
    @hookimpl
    def startup(self):
        print("AUTOCOMPLETE STARTUP")
        self.debug_db_status()
        
    @hookimpl
    def abandon_conversation(self):
        self.clear_input()
        
    @hookimpl
    def restart_asr(self):
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
                        asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                        asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master"))
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
                elif message_dict.get("msg"):
                    asyncio.create_task(self.pm.trigger_hook(hook_name="reset_conversation_timeout"))
                    input_value = message_dict.get("msg")
                    if input_value:
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
                "SELECT id, hits FROM predictions WHERE input = ? AND completion = ?",
                (input_text, completion)
            )
            
            self.logger.info(f"Query result: {result}")
            
            if result and len(result) > 0:
                # Update existing prediction hit count
                prediction_id = result[0]['id']
                hits = result[0]['hits'] + 1
                self.logger.info(f"Updating existing prediction (ID: {prediction_id}) with hits: {hits}")
                
                # The issue might be here - let's fix the UPDATE statement
                update_result = await self.db_execute(
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
            # Get exact matches first
            result = await self.db_execute(
                "SELECT input, completion, hits FROM predictions WHERE input = ? ORDER BY hits DESC LIMIT ?",
                (input_text, limit)
            )
            
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
        health_state=self.global_settings.get_health_state()
        bio_name=self.bio_name
        start_time = time.time()
        print("AUTOCOMPLETE PREDICTIONS")
        dynamic_context = self.get_dynamic_context()
        print(f"DYNAMIC CONTEXT IS {dynamic_context}")
        conversation = dynamic_context.get("conversation")
        print(f"CONVERSATION IS : {conversation}")
        assistant_type = "autocomplete"
        static_context = await self.pm.trigger_hook(
            hook_name="query_rag", 
            query_text=msg, 
            store_types=[0,1], 
            return_chunk_ids=True
        )
        # Get successful predictions for this input
        successful_predictions = await self.format_successful_predictions(msg)
        
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(
            bio_name=bio_name,
            health_state=health_state,
            static_context=static_context, 
            dynamic_context=dynamic_context, 
            successful_predictions=successful_predictions,
            input=msg
        )       
        print(f"FINAL HUMAN PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
        llm.set_json_schema(Answers)
        answers = llm.invoke(system_prompt,prompt)
        print(f"TYPE = {type(answers)}, ANSWERS: {answers}")
        answers_dict = answers.dict()
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
    answers: List[str]