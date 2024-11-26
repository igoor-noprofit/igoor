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

PROMPT_TEMPLATE = """
{system_prompt}

Pour répondre tu peux utilisers le contexte statique extrait des documents sur la vie de la personne :

{static_context}

---
Si besoin utilise aussi les infos du contexte dynamique suivant :

{dynamic_context}
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
    
    @hookimpl
    def startup(self):
        print("FLOW STARTUP")
        # self.test_queries()
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_in_executor(None, self._startup_async)
    
    async def _startup_async(self):
        print("sending status ready")
        await self.wait_for_socket_and_send("ready")
        self.send_test_json()
    
    '''   
    def send_test_json(self):
        print ("Sending test json")
        self.send_message_to_frontend([{"Joie":"Oui, j'adore le gâteau de riz !"},{"Anticipation":"Je me demande si on peut en manger à la plage ?"},{"Confiance":"Je suis sûr que ma famille en a préparé pour notre sortie"}])
    ''' 

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
                    asyncio.create_task(self.pm.trigger_hook(hook_name="abandon_conversation"))
                else:
                    print("Unrecognized action in incoming message.")
                    
        except json.JSONDecodeError:
            print("Received message is not valid JSON.")
            return
    '''
    Receives msg from speaker
    Transmits it to RAG systems
    Retrieves context
    Fills prompt
    Performs LLM query
    '''
    @hookimpl
    async def asr_msg(self, msg: str) -> None:
        start_time = time.time()
        print(f"QUERYING RAG WITH: {msg}")
        static_context = await(self.query_rag_async(msg))
        # print(f"STATIC CONTEXT IS : {static_context}")
        dynamic_context = self.get_dynamic_context()
        # Remove the conversation attribute from dynamic context
        conversation = dynamic_context.get("conversation")
        del dynamic_context["conversation"]
        assistant_type = "flow"
        system_prompt = self.prompts.get_system_prompt("fr_FR", assistant_type) 
        # print(f"SYSTEM PROMPT IS : {system_prompt}")   
        pm = PromptManager(template=PROMPT_TEMPLATE)
        dynamic_context = dynamic_context
        prompt = pm.create_prompt(system_prompt=system_prompt, static_context=static_context, dynamic_context=dynamic_context, conversation=conversation)       
        print(f"FINAL PROMPT : {prompt}")
        llm = LLMManager(self.settings.get("provider"), self.settings.get("api_key"), self.settings.get("model_name"))
        answers = llm.invoke(prompt)
        end_time = time.time()
        print(f"Time taken for processing: {end_time - start_time} seconds")
        self.send_message_to_frontend(answers.content) 
        
    def get_dynamic_context(self):
        return context_manager.get_context()

    async def query_rag_async(self, msg: str):
        result = await self.pm.trigger_hook(hook_name="query_rag", query_text=msg)
        return result
        
    def update_status(self, status):
        """This method will be called when the status changes."""
        print(f"Flow plugin received new status: {status}")
        
    
    def test_queries(self) -> None:
        queries = [
            "Q: Comment s'appelle tes fils",
            "Q: Tu te souviens de l'expo Drosephilia",
            "Q: Combien d'enfants tu as",
            "Q: Comment s'appelle ta femme",
            "Q: Quels sont tes réalisateurs préférés",
            "Q: Est-ce que t'aimes Tarantino",
        ]
        for query in queries:
            asyncio.run(self.asr_msg(query))
    
    
    '''
        
    @hookimpl
    def activate(self):
        print ("Activating flow")  
        
    @hookimpl
    def deactivate(self):
        print("Deactivating FLOW") 
    '''

    