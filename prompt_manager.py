from langchain.prompts import ChatPromptTemplate
import time

PROMPT_TEMPLATE = """
{system_prompt}

Réponds en utilisant aussi le contexte suivant:

{context}

---

Réponds en utilisant aussi le contexte ci-dessus à la question: {question}
"""
class PromptManager:
    def __init__(self, assistant_type, system_prompt_text, context_text, query_text):
        
        self.prompt_template = ChatPromptTemplate.from_template(prompt_template)
        self.system_prompt_text = system_prompt_text
        self.context_text = context_text
        self.query_text = query_text

    def format_prompt(self):
        prompt_format_start_time = time.time()
        prompt = self.prompt_template.format(
            system_prompt=self.system_prompt_text, 
            context=self.context_text, 
            question=self.query_text
        )
        prompt_format_end_time = time.time()
        print("************** PROMPT *******************")
        print(prompt)
        print("************* END PROMPT ****************")
        print(f"Prompt formatting time: {prompt_format_end_time - prompt_format_start_time:.2f} seconds")
        return prompt
    
        