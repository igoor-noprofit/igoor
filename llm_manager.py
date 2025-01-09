from langchain_groq import ChatGroq# Import other chat classes as needed
import logging,os,time
from settings_manager import SettingsManager
class LLMManager:
    def __init__(self, provider, api_key, model_name, **kwargs):
        self.global_settings = SettingsManager();
        ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
        self.provider = provider or ai.get("provider")
        self.api_key = api_key or ai.get("api_key")
        self.model_name = model_name or ai.get("model_name")
        self.temperature = kwargs.get("temperature", 1) or ai.get("temperature")
        self.chat_instance = self._create_chat()
        self.json_schema=False
        self.log_folder = kwargs.get("log_folder", None)
        # Set up logging
        self._setup_logging()

    def _create_chat(self):
        if self.provider == "groq":
            return ChatGroq(temperature=self.temperature, groq_api_key=self.api_key, model_name=self.model_name)
        elif self.provider == "openai":
            return ChatOpenAI(temperature=self.temperature, openai_api_key=self.api_key, model_name=self.model_name)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _setup_logging(self):
        if self.log_folder:
            os.makedirs(self.log_folder, exist_ok=True)
            log_file = os.path.join(self.log_folder, 'llm_manager.log')
            print(f"Log_file:{log_file}")
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                encoding='utf-8'  # Specify UTF-8 encoding
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                encoding='utf-8'  # Specify UTF-8 encoding
            )
            
    def set_json_schema(self, schema):
        """Sets the JSON schema for structured output."""
        try:
            self.json_schema = True
            self.structured_chat_instance=self.chat_instance.with_structured_output(schema)
        except Exception as e:
            print("Exception setting JSON schema")
            return e
        
    # ... existing code ...
    def invoke(self, system_prompt, prompt, retries=3):
        messages = [
            ("system", system_prompt),
            ("human", prompt)
        ]
        logging.info(f"Invoking with system prompt: {system_prompt} and user prompt: {prompt}")
        attempt = 0
        while attempt < retries:
            try:
                if(self.json_schema):
                    return self.structured_chat_instance.invoke(messages)
                else:
                    logging.info(f"Invoking without JSON schema")
                    return self.chat_instance.invoke(messages)
                logging.info(f"Invocation successful. Result: {result}")
                
            except Exception as e:
                attempt += 1
                last_exception = e
                logging.error(f"Invocation failed on attempt {attempt}: {str(e)}")
                
                if attempt < retries:
                    # Add exponential backoff delay
                    delay = 0.5 ** attempt  # 2, 4, 8 seconds
                    logging.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                else:
                    logging.error("Max retries reached.")
                    # Return a dictionary with error information instead of the raw exception
                    return {
                        "error": True,
                        "message": str(last_exception),
                        "type": type(last_exception).__name__
                    }
