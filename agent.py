import os
import global_settings
from rich import print
from prompts import SYSTEM_PROMPT, TASK_COMPLETION_CHECK_PROMPT
import memory_management

class Agent():

    def __init__(self, queue, telegram):
        self.queue = queue
        self.telegram = telegram
        self.system_prompt = SYSTEM_PROMPT.format(
            working_directory=global_settings.working_directory,
            soul=self.load_soul(),
            user_preferences=self.load_user_preferences()
        )
        self.loaded_memories = set()
        self.messages = []
    
    def load_soul(self):
        soul_path = os.path.join(global_settings.working_directory, "soul.md")
        soul_path = os.path.expanduser(soul_path)
        with open(soul_path, "r") as f:
            return f.read()
        return ""
    
    def load_user_preferences(self):
        user_pref_path = os.path.join(global_settings.working_directory, "user_preferences.md")
        user_pref_path = os.path.expanduser(user_pref_path)
        with open(user_pref_path, "r") as f:
            return f.read()
        return ""
    
    def generate(self, model, messages, tools=None):
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def process_response(self, response):
        raise NotImplementedError("This method should be implemented by subclasses")
    
    def compress_conversation(self):
        raise NotImplementedError("This method should be implemented by subclasses")

    def check_task_completion(self):
        raise NotImplementedError("This method should be implemented by subclasses")

    def query_and_load_memories(self, user_msg):
        l = []
        related_memories = memory_management.query_memory(user_msg)
        if related_memories and related_memories['documents']:
            for i in range(len(related_memories['documents'][0])):
                _id = related_memories['ids'][0][i]
                if _id not in self.loaded_memories:
                    self.loaded_memories.add(_id)
                    l.append(related_memories['documents'][0][i])
        return l

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

            related_memories = self.query_and_load_memories(user_msg)
            if related_memories:
                formatted_memories = "\n".join([f"- {mem}" for mem in related_memories])
                print(f"[blue]Found related memories for the user message:\n{formatted_memories}[/blue]")
                self.messages.append({
                    "role": "system",
                    "content": f"Load relevant facts from memory:\n{formatted_memories}"
                })

            while True:
                response, input_tokens, output_tokens = self.generate_next_step(
                    self.model, self.messages, tools=self.tool_definitions
                )

                if input_tokens > global_settings.compression_threshold:
                    print(f"[purple]Input tokens ({input_tokens}) exceed compression threshold. Compressing conversation...[/purple]")
                    self.compress_conversation()

                has_tool_calls= self.process_response(response)
                if has_tool_calls:
                    continue
                task_done, to_do = self.check_task_completion()
                if task_done:
                    print("[green]Task completed. Waiting for new instructions...[/green]")
                    self.update_sop()
                    break
                else:
                    self.messages.append({
                        "role": "system",
                        "content": f"Task is not completed. Remaining to do: {to_do}"
                    })
    
    def update_sop(self):
        # do in sub-agent
        pass
