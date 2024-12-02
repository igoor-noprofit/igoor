from langchain_groq import ChatGroq# Import other chat classes as needed
import logging,os
class LLMManager:
    def __init__(self, provider, api_key, model_name, **kwargs):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = kwargs.get("temperature", 1)
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
                logging.error(f"Invocation failed on attempt {attempt}: {e}")
                if attempt >= retries:
                    logging.error("Max retries reached. Returning the exception.")
                    return e
                # Optionally, you could add a delay here before retrying
