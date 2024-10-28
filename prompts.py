import json
import os

class AssistantPrompts:
    def __init__(self, locale_dir, language):
        self.locale_dir = locale_dir + language
        self.assistant_prompts = self.load_prompts()
        if not self.assistant_prompts:
            return False
            # print(self.assistant_prompts.get("flow", {}).get("system", ""))

    def load_prompts(self):
        assistant_prompts = {}
        prompts_file = os.path.join(self.locale_dir, "prompts.json")
        if os.path.exists(prompts_file):
            with open(prompts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            print("ERROR: Prompt file not found @ " + prompts_file)
        return False

    def get_system_prompt(self, language, assistant_type):
        return self.assistant_prompts.get(assistant_type, {}).get("system", "")