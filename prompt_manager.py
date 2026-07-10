from langchain.prompts import ChatPromptTemplate
import time

class PromptManager:
    def __init__(self, template: str):
        """
        Initializes the PromptManager with a template.

        :param template: The prompt template with placeholders.
        """
        try:
            self.prompt_template = ChatPromptTemplate.from_template(template)
        except Exception as e:
            print(f"Error initializing ChatPromptTemplate: {e}")
            raise

    def partial(self, **kwargs):
        """
        Pre-fill static variables into the template.
        Call this once at init/settings-change time to avoid
        re-merging unchanging values on every hot-path call.
        Returns self for chaining.
        """
        self.prompt_template = self.prompt_template.partial(**kwargs)
        return self

    def create_prompt(self, **kwargs) -> str:
        """
        Binds variables in the given template using the provided keyword arguments.

        :param kwargs: Key-value pairs where the key is the placeholder name and the value is the value to replace it with.
        :return: The template with placeholders replaced by actual values.
        """
        try:
            bound_prompt = self.prompt_template.format(**kwargs)
        except Exception as e:
            print(f"Error binding prompt template: {e}")
            raise ValueError(f"Failed to bind prompt template: {e}") from e
        return bound_prompt