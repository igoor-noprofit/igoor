from version import __appname__, __version__, __codename__
from langchain_groq import ChatGroq  # Import other chat classes as needed
from langchain.callbacks import StdOutCallbackHandler
import langchain
langchain.debug = True  # Enable debug mode for LangChain
import os, time
from settings_manager import SettingsManager
from utils import setup_logger, setup_jsonl_logger


class LLMManager:
    def __init__(self, provider, api_key, model_name, **kwargs):
        # Setup logger
        self.logger = setup_logger('llm_manager', os.path.join(os.getenv('APPDATA'), __appname__))
        
        self.global_settings = SettingsManager()
        ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})
        self.provider = provider or ai.get("provider")
        self.api_key = api_key or ai.get("api_key")
        self.model_name = model_name or ai.get("model_name")
        self.temperature = kwargs.get("temperature") or ai.get("temperature")
        self.chat_instance = self._create_chat()
        self.json_schema = False
        # Setup dedicated logger for LLM invocations
        self.invocation_logger = setup_jsonl_logger('llm_invocations', os.path.join(os.getenv('APPDATA'), __appname__))

    def _create_chat(self):
        if self.provider == "groq":
            self.logger.info(f"Creating Groq chat instance with model: {self.model_name}")
            base_chat = ChatGroq(
                temperature=self.temperature, 
                groq_api_key=self.api_key, 
                model_name=self.model_name, 
                callbacks=[StdOutCallbackHandler()]
            )
            # Return the instance with tools disabled by default
            return base_chat.bind(tool_choice="none")
        elif self.provider == "openai":
            self.logger.info(f"Creating OpenAI chat instance with model: {self.model_name}")
            return ChatOpenAI(temperature=self.temperature, openai_api_key=self.api_key, model_name=self.model_name)
        else:
            error_msg = f"Unsupported provider: {self.provider}"
            self.logger.error(error_msg) 
            raise ValueError(error_msg)
            
    def set_json_schema(self, schema):
        """Sets the JSON schema for structured output."""
        try:
            self.json_schema = True
            self.structured_chat_instance = self.chat_instance.with_structured_output(schema)
        except Exception as e:
            self.logger.error(f"Exception setting JSON schema: {e}")
            return e
    
    def get_no_tools_instance(self):
        """Returns a chat instance with tools explicitly disabled."""
        return self.chat_instance.bind(tool_choice="none")
    
    def invoke(self, system_prompt, prompt, retries=3):
        messages = [
            ("system", system_prompt),
            ("human", prompt)
        ]
        attempt = 0
        while attempt < retries:
            try:
                if self.json_schema:
                    result = self.structured_chat_instance.invoke(messages)
                    # Generic conversion of any Pydantic model to dict
                    if hasattr(result, 'model_dump'):
                        result_dict = result.model_dump()
                    elif hasattr(result, 'dict'):
                        result_dict = result.dict()
                    else:
                        result_dict = str(result)
                    response_content = result
                    # Generic conversion of any Pydantic model to dict for logging
                    if hasattr(result, 'model_dump'):
                        response_log_content = result.model_dump()
                    elif hasattr(result, 'dict'):
                        response_log_content = result.dict()
                    else:
                        response_log_content = str(result)
                    # self.logger.info(f"Structured LLM Response:\n{json.dumps(response_log_content, indent=2, ensure_ascii=False)}") # Keep regular log minimal
                else:
                    response_content = self.chat_instance.invoke(messages)
                    response_log_content = str(response_content)
                    # self.logger.info(f"Unstructured LLM Response:\n{str(response_content)}") # Keep regular log minimal
                
                # Log invocation details to JSONL file
                log_data = {
                    "p": self.provider,
                    "m": self.model_name,
                    "t": self.temperature,
                    "sys": system_prompt,
                    "usr": prompt,
                    "resp": response_log_content
                }
                self.invocation_logger.info(log_data)
                
                return response_content
                
            except Exception as e:
                print(f"Exception in LLMManager.invoke: {e}")
                if hasattr(e, 'response'):
                    print(f"Exception response: {e.response}")
                if hasattr(e, 'body'):
                    print(f"Exception body: {e.body}")
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
                    
                    self.logger.warning(f"Rate limit reached. Suggested wait time: {wait_time} seconds")
                    return {
                        "error": True,
                        "type": "RateLimitError",
                        "message": error_message,
                        "wait_time": wait_time
                    }
                
                self.logger.error(f"Invocation failed on attempt {attempt}: {error_message}")
                
                if attempt < retries:
                    delay = 2 ** attempt  # 2, 4, 8 seconds
                    self.logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached.")
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