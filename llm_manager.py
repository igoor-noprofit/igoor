from version import __appname__, __version__, __codename__
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
        # Prefer an explicitly passed temperature (even if falsy like 0); otherwise use saved settings.
        if "temperature" in kwargs:
            temp_raw = kwargs["temperature"]
        else:
            temp_raw = ai.get("temperature")
        try:
            self.temperature = float(temp_raw)
        except (TypeError, ValueError):
            self.logger.warning(f"Invalid temperature value {temp_raw!r}; falling back to 0.7")
            self.temperature = 0.7
        # Get reasoning_effort from settings
        self.reasoning_effort = ai.get("reasoning_effort", "low")
        self.chat_instance = self._create_chat()
        self.json_schema = False
        # Setup dedicated logger for LLM invocations
        self.invocation_logger = setup_jsonl_logger('llm_invocations', os.path.join(os.getenv('APPDATA'), __appname__))

    def _create_chat(self):
        if self.provider == "groq":
            '''
            self.logger.info(f"Creating Groq chat instance with model: {self.model_name}")
            base_chat = ChatGroq(
                temperature=self.temperature, 
                groq_api_key=self.api_key, 
                model_name=self.model_name, 
                callbacks=[StdOutCallbackHandler()]
            )
            # Return the instance with tools disabled by default
            return base_chat.bind(tool_choice="none")
            '''
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
            self.schema_model = schema  # Store the Pydantic model
            if self.provider == "groq":
                # For Groq SDK, we use the schema at invocation time
                self.structured_chat_instance = None
            else:
                self.structured_chat_instance = self.chat_instance.with_structured_output(schema)
        except Exception as e:
            self.logger.error(f"Exception setting JSON schema: {e}")
            return e

    def get_no_tools_instance(self):
        """Returns a chat instance with tools explicitly disabled."""
        return self.chat_instance.bind(tool_choice="none")
    
    def invoke(self, system_prompt, prompt, retries=3, reasoning_effort=None):
        import json
        attempt = 0
        last_exception = None
        while attempt < retries:
            try:
                reasoning_log_content = ""  # Initialize reasoning_log_content
                # GPT-OSS models use include_reasoning, not reasoning_format
                is_gpt_oss = self.model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
                if self.provider == "groq" and self.json_schema and hasattr(self, "schema_model"):
                    # Import Groq SDK at runtime
                    from groq import Groq
                    client = Groq(api_key=self.api_key)
                    # Prepare messages in OpenAI format
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                    schema = self.schema_model

                    if self.model_name == "llama-3.3-70b-versatile" or is_gpt_oss:
                        # Use json_object mode - more compatible with reasoning models
                        # GPT-OSS reasoning + json_schema doesn't work reliably
                        response_format={
                            "type": "json_object"
                        }
                    else:
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema.__name__,
                                "schema": schema.model_json_schema(),
                                "strict": False
                            }
                        }
                    call_args = {
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": self.temperature,
                        "response_format": response_format
                    }
                    # Note: GPT-OSS reasoning + JSON schema mode doesn't work reliably
                    # If user wants reasoning, they should use a non-reasoning model or accept JSON mode without schema
                    response = client.chat.completions.create(**call_args)
                    raw_content = response.choices[0].message.content
                    if is_gpt_oss and hasattr(response.choices[0].message, 'reasoning') and response.choices[0].message.reasoning:
                        reasoning_log_content = response.choices[0].message.reasoning
                        print(f"REASONING: {response.choices[0].message.reasoning}")
                    if not raw_content:
                        raise ValueError("Model returned empty content") 
                    print("Groq raw model output:", raw_content)
                    raw_result = json.loads(raw_content or "{}")
                    result = schema.model_validate(raw_result)
                    response_content = result
                    response_log_content = result.model_dump() if hasattr(result, "model_dump") else str(result)
                elif self.json_schema:
                    # LangChain structured output
                    result = self.structured_chat_instance.invoke([
                        ("system", system_prompt),
                        ("human", prompt)
                    ])
                    response_content = result
                    response_log_content = result.model_dump() if hasattr(result, "model_dump") else str(result)
                else:
                    # Unstructured output
                    response_content = self.chat_instance.invoke([
                        ("system", system_prompt),
                        ("human", prompt)
                    ])
                    response_log_content = str(response_content)

                # Log invocation details to JSONL file
                log_data = {
                    "p": self.provider,
                    "m": self.model_name,
                    "t": self.temperature,
                    "sys": system_prompt[:80],
                    "usr": prompt
                }
                # Add reasoning_effort if used (GPT-OSS models)
                if is_gpt_oss:
                    log_data["re"] = reasoning_effort if reasoning_effort is not None else self.reasoning_effort
                # Add reasoning_log_content if it's not empty
                if reasoning_log_content:
                    log_data["reason"] = reasoning_log_content
                log_data["resp"] = response_log_content
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
                    import re
                    wait_time = 15 * 60  # default 15 minutes in seconds
                    time_match = re.search(r'try again in (\d+)m([\d.]+)s', error_message)
                    if time_match:
                        minutes, seconds = time_match.groups()
                        wait_time = int(minutes) * 60 + float(seconds)

                    self.logger.warning(f"Rate limit reached. Suggested wait time: {wait_time} seconds")
                    # Log the error to JSONL
                    self.invocation_logger.info({
                        "p": self.provider,
                        "m": self.model_name,
                        "t": self.temperature,
                        "sys": system_prompt[:80],
                        "usr": prompt,
                        "error": True,
                        "err_type": "RateLimitError",
                        "wait_time": wait_time
                    })
                    return {
                        "error": True,
                        "type": "RateLimitError",
                        "message": error_message,
                        "wait_time": wait_time
                    }

                self.logger.error(f"Invocation failed on attempt {attempt}: {error_message}")

                if attempt < retries:
                    delay = 0.5 ** attempt  # 0.5, 0.25, 0.125 seconds
                    self.logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached.")
                    # Log the error to JSONL
                    self.invocation_logger.info({
                        "p": self.provider,
                        "m": self.model_name,
                        "t": self.temperature,
                        "sys": system_prompt[:80],
                        "usr": prompt,
                        "error": True,
                        "err_type": type(last_exception).__name__,
                        "err_msg": error_message[:200]
                    })
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