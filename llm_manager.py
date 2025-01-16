from langchain_groq import ChatGroq# Import other chat classes as needed
import logging,os,time,json
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
        
    def invoke(self, system_prompt, prompt, retries=3):
        ''' TEST ERROR 
        error_message = "Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile`. Please try again in 15m2.651s.', 'type': '', 'code': 'rate_limit_exceeded'}}"
        wait_time = 15 * 60
        return {
            "error": True,
            "type": "RateLimitError",
            "message": error_message,
            "wait_time": wait_time
        }
        '''
        messages = [
            ("system", system_prompt),
            ("human", prompt)
        ]
        logging.info(f"Invoking with system prompt: {system_prompt} and user prompt: {prompt}")
        attempt = 0
        while attempt < retries:
            try:
                if(self.json_schema):
                    result = self.structured_chat_instance.invoke(messages)
                    # Generic conversion of any Pydantic model to dict
                    if hasattr(result, 'model_dump'):  # For Pydantic v2
                        result_dict = result.model_dump()
                    elif hasattr(result, 'dict'):      # For Pydantic v1
                        result_dict = result.dict()
                    else:
                        result_dict = str(result)
                    logging.info(f"Invocation successful. Result:\n{json.dumps(result_dict, indent=2, ensure_ascii=False)}")
                else:
                    logging.info(f"Invoking without JSON schema")
                    result = self.chat_instance.invoke(messages)
                    logging.info(f"Invocation successful. Result:\n{json.dumps(str(result), indent=2, ensure_ascii=False)}")
                return result
                
            except Exception as e:
                attempt += 1
                last_exception = e
                error_message = str(e)
                
                # Check if this is a rate limit error
                is_rate_limit = (
                    "rate limit" in error_message.lower() or 
                    "429" in error_message
                )
                if is_rate_limit:
                    # Extract wait time from error message if available
                    import re
                    wait_time = 15 * 60  # default 15 minutes in seconds
                    time_match = re.search(r'try again in (\d+)m([\d.]+)s', error_message)
                    if time_match:
                        minutes, seconds = time_match.groups()
                        wait_time = int(minutes) * 60 + float(seconds)
                    
                    logging.warning(f"Rate limit reached. Suggested wait time: {wait_time} seconds")
                    return {
                        "error": True,
                        "type": "RateLimitError",
                        "message": error_message,
                        "wait_time": wait_time
                    }
                
                logging.error(f"Invocation failed on attempt {attempt}: {error_message}")
                
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
                        "message": error_message,
                        "type": type(last_exception).__name__
                    }
                    
    @staticmethod                   
    def is_error_response(response) -> tuple[bool, dict]:
        """
        Checks if the LLM response is an error dictionary.
        Returns a tuple of (is_error: bool, error_info: dict)
        """
        if isinstance(response, dict) and response.get("error"):
            error_info = {
                "type": response.get("type"),
                "message": response.get("message"),
                "wait_time": response.get("wait_time")  # Will be None for non-rate-limit errors
            }
            return True, error_info
        return False, {}
