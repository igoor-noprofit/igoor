from version import __appname__, __version__, __codename__
import langchain
langchain.debug = True  # Enable debug mode for LangChain
import os, time
from settings_manager import SettingsManager
from utils import setup_logger, setup_jsonl_logger
from langchain_openai import ChatOpenAI


# Default base URLs for popular OpenAI-compatible providers
PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openai": None,  # Default OpenAI endpoint
    "ollama": "http://localhost:11434/v1",
    "ollama-cloud": "https://api.ollama.com/v1",  # Ollama cloud
    "lmstudio": "http://localhost:1234/v1",
}


class LLMManager:
    def __init__(self, provider, api_key, model_name, base_url=None, **kwargs):
        # Setup logger
        self.logger = setup_logger('llm_manager', os.path.join(os.getenv('APPDATA'), __appname__))

        self.global_settings = SettingsManager()
        ai = self.global_settings.get_nested(["plugins", "onboarding", "ai"], default={})

        # Get provider - support both old "groq"/"openai" and new unified approach
        self.provider = provider or ai.get("provider", "openai")

        # Get API key
        self.api_key = api_key or ai.get("api_key")

        # Get model name
        self.model_name = model_name or ai.get("model_name")

        # Get base_url - priority: explicit param > settings > provider defaults
        if base_url is not None:
            self.base_url = base_url
        elif ai.get("base_url"):
            self.base_url = ai.get("base_url")
        elif self.provider in PROVIDER_BASE_URLS:
            self.base_url = PROVIDER_BASE_URLS[self.provider]
        else:
            self.base_url = None

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
        """Create a chat instance using OpenAI SDK with configurable base_url."""
        self.logger.info(f"Creating chat instance - provider: {self.provider}, model: {self.model_name}, base_url: {self.base_url}")

        return ChatOpenAI(
            temperature=self.temperature,
            openai_api_key=self.api_key,
            model_name=self.model_name,
            base_url=self.base_url  # None uses default OpenAI endpoint
        )

    def set_json_schema(self, schema):
        """Sets the JSON schema for structured output."""
        try:
            self.json_schema = True
            self.schema_model = schema  # Store the Pydantic model

            # Check if this is OpenAI (default endpoint)
            is_openai = self.base_url is None or "api.openai.com" in (self.base_url or "")

            if is_openai:
                # OpenAI supports strict structured output with schema validation
                self.structured_chat_instance = self.chat_instance.with_structured_output(schema, strict=True)
                self._use_manual_json = False
            else:
                # For other providers (Groq, Cerebras, etc.), we handle JSON ourselves
                # Don't use LangChain's with_structured_output - it doesn't work well
                self.structured_chat_instance = None
                self._use_manual_json = True
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
                reasoning_log_content = ""
                cache_log = {}

                if self.json_schema:
                    if getattr(self, "_use_manual_json", False):
                        # Manual JSON mode for non-OpenAI providers
                        # Add JSON format instruction to system prompt
                        schema_json = self.schema_model.model_json_schema()
                        json_instruction = f"\n\nIMPORTANT: Respond ONLY with valid JSON matching this schema:\n{json.dumps(schema_json, indent=2)}\n\nDo not include any text outside the JSON object."

                        response = self.chat_instance.invoke([
                            ("system", system_prompt + json_instruction),
                            ("human", prompt)
                        ])

                        # Parse JSON from response
                        raw_content = response.content
                        parsed = self._parse_json_response(raw_content)
                        if parsed:
                            # Validate with Pydantic
                            result = self.schema_model.model_validate(parsed)
                            response_content = result
                            response_log_content = result.model_dump() if hasattr(result, "model_dump") else str(result)
                        else:
                            raise ValueError(f"Failed to parse JSON from response: {raw_content}")
                    elif hasattr(self, "structured_chat_instance") and self.structured_chat_instance:
                        # OpenAI structured output
                        result = self.structured_chat_instance.invoke([
                            ("system", system_prompt),
                            ("human", prompt)
                        ])
                        response_content = result
                        response_log_content = result.model_dump() if hasattr(result, "model_dump") else str(result)
                else:
                    # Unstructured output
                    response = self.chat_instance.invoke([
                        ("system", system_prompt),
                        ("human", prompt)
                    ])
                    response_content = response
                    response_log_content = str(response_content)

                    # Try to extract provider-specific metadata (reasoning, cache info)
                    if hasattr(response, 'response_metadata'):
                        metadata = response.response_metadata

                        # Check for reasoning in token_usage (some providers include it)
                        if 'token_usage' in metadata:
                            usage = metadata['token_usage']

                            # Check for reasoning tokens (varies by provider)
                            if isinstance(usage, dict):
                                if 'reasoning_tokens' in usage:
                                    reasoning_log_content = f"Reasoning tokens: {usage['reasoning_tokens']}"
                                    self.logger.info(f"Reasoning tokens used: {usage['reasoning_tokens']}")

                                # Check for cache information (Groq, etc.)
                                prompt_tokens = usage.get('prompt_tokens', 0)
                                cached_tokens = 0

                                # Try different cache field names used by providers
                                if 'cached_tokens' in usage:
                                    cached_tokens = usage['cached_tokens']
                                elif 'prompt_tokens_details' in usage:
                                    ptd = usage['prompt_tokens_details']
                                    if isinstance(ptd, dict):
                                        cached_tokens = ptd.get('cached_tokens', 0)

                                if cached_tokens > 0 and prompt_tokens > 0:
                                    hit_rate = (cached_tokens / prompt_tokens * 100)
                                    self.logger.info(f"Cache: {cached_tokens}/{prompt_tokens} tokens cached → {hit_rate:.1f}%")
                                    cache_log = {
                                        "cached_tokens": cached_tokens,
                                        "prompt_tokens": prompt_tokens,
                                        "cache_hit_pct": round(hit_rate, 1)
                                    }

                # Log invocation details to JSONL file
                log_data = {
                    "p": self.provider,
                    "m": self.model_name,
                    "base_url": self.base_url,
                    "t": self.temperature,
                    "sys": system_prompt[:80],
                    "usr": prompt
                }

                if reasoning_log_content:
                    log_data["reason"] = reasoning_log_content
                if cache_log:
                    log_data.update(cache_log)
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
                        "base_url": self.base_url,
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
                        "base_url": self.base_url,
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

    def _parse_json_response(self, content):
        """Extract and parse JSON from LLM response."""
        import json
        import re

        # Try direct parse first
        try:
            return json.loads(content)
        except:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except:
                pass

        # Try to find JSON object in the response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass

        return None

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

    @staticmethod
    def get_supported_providers():
        """Returns a list of supported providers with their default base URLs."""
        return PROVIDER_BASE_URLS.copy()
