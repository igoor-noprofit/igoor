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
            
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
    '''
    async def predict_word(self, input_text: str) -> List[str]:
        # Get the last word being typed
        words = input_text.split()
        current_word = words[-1] if words else ""
        
        if len(current_word) < 2:  # Only predict for words longer than 1 character
            return []
            
        # Get similar words using FastText
        similar_words = self.word_model.get_nearest_neighbors(current_word, k=5)
        # Return just the words, not the scores
        return [word for score, word in similar_words]   
    ''' 
    
    '''
    Receives msg from autocomplete input
    Transmits it to RAG systems
    Retrieves context
    Fills prompt
    Performs LLM query
    '''
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
        static_context = await(self.query_rag_async(msg))
        # print(f"STATIC CONTEXT IS : {static_context}")
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        # print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        prompt = pm.create_prompt(bio_name=bio_name,health_state=health_state,static_context=static_context, dynamic_context=dynamic_context, input=msg)       
        print(f"FINAL HUMAN PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
        llm.set_json_schema(Answers)
        answers = llm.invoke(system_prompt,prompt)
        print(f"TYPE = {type(answers)}, ANSWERS: {answers}")
        answers_dict = answers.dict()
        if answers_dict.get("answers"):
            self.send_message_to_frontend(answers.json(), "flow") 
        else:
            print("NO PREDICTIONS RECEIVED")
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

class Answers(BaseModel):
    answers: List[str]
