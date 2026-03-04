import os
import global_settings
from rich import print
from prompts import SYSTEM_PROMPT, SUMMARIZR_SOP

class Agent():

    def __init__(self, queue, telegram):
        self.queue = queue
        self.telegram = telegram
        self.system_prompt = SYSTEM_PROMPT.format(
            working_directory=global_settings.working_directory,
            soul=self.load_soul(),
            user_preferences=self.load_user_preferences()
        )
    
    def load_soul(self):
        soul_path = os.path.join(global_settings.working_directory, "soul.md")
        if os.path.exists(soul_path):
            with open(soul_path, "r") as f:
                return f.read()
        return ""
    
    def load_user_preferences(self):
        user_pref_path = os.path.join(global_settings.working_directory, "user_preferences.md")
        if os.path.exists(user_pref_path):
            with open(user_pref_path, "r") as f:
                return f.read()
        return ""
    
    def complete(self):
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def process_response(self, response):
        raise NotImplementedError("This method should be implemented by subclasses")

    def loop(self):
        print("[green]Agent is ready to receive your instructions...[/green]")
        while True:
            user_msg = self.queue.get()
            user_msg = user_msg.strip()
            if user_msg == "":
                continue
            self.messages.append({
                "role": "user",
                "content": user_msg
            })

            while True:
                response = self.complete()
                task_done = self.process_response(response)
                if task_done:
                    break