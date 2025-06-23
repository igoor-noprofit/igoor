from settings_manager import SettingsManager
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from concurrent.futures import ThreadPoolExecutor
from prompt_manager import PromptManager
from context_manager import context_manager
from prompts import AssistantPrompts
from settings_manager import SettingsManager
from llm_manager import LLMManager
import asyncio,json,time,os
from pydantic import BaseModel
from typing import List
from utils import normalize_filter_by_timeframe_result

class Daily(Baseplugin):  
    def __init__(self, plugin_name,pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        # self.prompts=AssistantPrompts("locales/",self.lang)
        self.prompts=self.get_my_prompts()
        print(f"PROMPTS LOADED: {self.prompts}")
        self.load_settings()
        bio = self.settings_manager.get_bio()
        self.bio_name = bio.get("name")
        self.daily_data = None
        
    def load_settings(self):
        self.settings = self.get_my_settings()
        
    def load_daily_data(self):
        if (not self.settings):
            current_file_dir = os.path.dirname(__file__)
            default_daily_file = os.path.join(current_file_dir, 'daily.json')
            self.logger.info("No settings found, using default daily data from daily.json")
            try:
                with open(default_daily_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.daily_data = data.get(self.lang, {})
                    self.settings_manager.update_plugin_settings('daily',self.daily_data)
                    return True
            except FileNotFoundError:
                print ("ERROR DAILY JSON NOT FOUND")
            
        else: 
            self.daily_data = self.settings 
    
    @hookimpl
    def startup(self):
        self.load_daily_data()
        
    @hookimpl
    def custom_save_settings(self, plugin_name:str,settings):
        print("CUSTOM SAVE SETTINGS CALLED with plugin_name:", plugin_name)
        print("AND SETTINGS:", settings)
        data={}
        data["needs"]=settings
        if plugin_name == self.plugin_name:
            self.logger.info(f"CUSTOM save settings for {plugin_name}: {data}")
            self.settings_manager.update_plugin_settings('daily',data)
            self.send_message_to_frontend({
                'dailyData': data
            })
            asyncio.create_task(self.send_switch_view_to_app(view="daily"))
            return True        
        
    @hookimpl
    def abandon_conversation(self):
        self.send_message_to_frontend({'backhome': True})
    
    async def startup_async(self):
        """Async startup tasks"""
        await self.send_message_to_frontend({
            'dailyData': self.daily_data
        })

    def process_incoming_message(self, message):
        try:
            message_data = json.loads(message)
            print(f"DAILY RECEIVED MSG:{message_data}")
            print(f"DAILY BACKEND RECEIVED MSG On WS: {message_data}")
            if message_data.get('socket') == 'ready':
                print(self.daily_data)
                # Send daily data to frontend
                self.send_message_to_frontend({
                    'dailyData': self.daily_data
                })
            # GENERATE  PHRASES AND IF APPLICABLE ABANDONS CONVERSATION
            elif message_data.get('action') == 'generatePhrases':
                asyncio.create_task(self.pm.trigger_hook(hook_name="abandon_conversation",cause="daily"))
                asyncio.create_task(self.generate_phrases(message_data))
                pass
            # SPEAKS THE CHOSEN PHRASE
            elif message_data.get('action') == "speak":
                    asyncio.create_task(self.send_switch_view_to_app(view="flow"))
                    msg = message_data.get("msg", "")
                    # Trigger hook in plugin manager with msg
                    asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                    asyncio.create_task(self.pm.trigger_hook(hook_name="add_msg_to_conversation", msg=msg, author="master",msg_input="daily"))    
        except json.JSONDecodeError:
            print(f"Invalid JSON message received: {message}")
        
    '''
    Receives msg from daily
    Transmits it to RAG systems
    Retrieves context
    Fills prompt
    Performs LLM query
    '''        
    async def generate_phrases(self, data: dict) -> None:
        if not isinstance(data, dict):
            print("Error: Data is not a dictionary")
            return
        health_state=self.settings_manager.get_health_state()
        bio_name=self.bio_name
        start_time = time.time()
        dynamic_context = self.get_dynamic_context().copy()
        print(f"DYNAMIC CONTEXT IS {dynamic_context}")
        # Remove the conversation attribute from dynamic context
        # conversation = dynamic_context.get("conversation")
        category=data.get("category")
        theme=data.get("theme")
        asyncio.create_task(self.pm.trigger_hook(hook_name="set_conversation_topic",topic=theme))
        chunk_ids = await(self.pm.trigger_hook(hook_name="query_rag", query_text=category + " " + theme, store_types=[0,1,2], return_chunk_ids=True))
        filtered_results = await self.pm.trigger_hook(
            hook_name="filter_by_timeframe", 
            preflow_dict={},
            docstore_ids_by_type=chunk_ids
        )
        # self.logger.info(f"FILTERED RESULTS: {filtered_results}")
        actual_filtered_results = normalize_filter_by_timeframe_result(filtered_results)
        # del dynamic_context["conversation"]
        assistant_type = "daily"
        system_prompt = self.prompts.get("daily", {}).get("system")
        print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=self.prompts.get("daily", {}).get("usr"))
        dynamic_context = dynamic_context
        prompt = pm.create_prompt(
            bio_name=bio_name,
            health_state=health_state,
            static_context='\n'.join(actual_filtered_results.get(0, [])), # Use actual_filtered_results
            long_term='\n'.join(actual_filtered_results.get(1, [])),  # Use actual_filtered_results
            short_term='\n'.join(actual_filtered_results.get(2, [])), # Use actual_filtered_results
            dynamic_context=dynamic_context, 
            category=category,
            theme=theme, 
            tags="",
            log_folder=self.plugin_folder)       
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
            
    def get_dynamic_context(self):
        return context_manager.get_context()
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")

class Answers(BaseModel):
    answers: List[str]
