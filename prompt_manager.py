from langchain.prompts import ChatPromptTemplate
import time

class PromptManager:
    def __init__(self, template: str):
        """
        Initializes the PromptManager with a template.

        :param template: The prompt template with placeholders.
        """
        self.prompt_template = ChatPromptTemplate.from_template(template)

    def create_prompt(self, **kwargs) -> str:
        """
        Binds variables in the given template using the provided keyword arguments.

        :param kwargs: Key-value pairs where the key is the placeholder name and the value is the value to replace it with.
        :return: The template with placeholders replaced by actual values.
        """
        bound_prompt = self.prompt_template.format(**kwargs)
        return bound_prompt