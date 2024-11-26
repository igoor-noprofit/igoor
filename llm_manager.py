from langchain_groq import ChatGroq# Import other chat classes as needed

class LLMManager:
    def __init__(self, provider, api_key, model_name, **kwargs):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = kwargs.get("temperature", 0)
        self.chat_instance = self._create_chat()

    def _create_chat(self):
        if self.provider == "groq":
            return ChatGroq(temperature=self.temperature, groq_api_key=self.api_key, model_name=self.model_name)
        elif self.provider == "openai":
            return ChatOpenAI(temperature=self.temperature, openai_api_key=self.api_key, model_name=self.model_name)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def invoke(self, system_prompt, prompt):
        messages = [
            (
                "system",
                system_prompt
            ),
            ("human", prompt),
        ]
        return self.chat_instance.invoke(messages)
