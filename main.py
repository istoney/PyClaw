import os
import json
import tools_hub
import initalize
import threading
import queue
import global_settings
import anthropic
from rich import print
from prompts import SYSTEM_PROMPT, SUMMARIZR_SOP
from client.openrouter import OpenRouterClient
from client.telegram import TelegramClient

class Agent():
    def __init__(self, queue, telegram):
        self.queue = queue
        self.telegram = telegram
        self.system_prompt = SYSTEM_PROMPT.format(
            working_directory=global_settings.working_directory,
            soul=self.load_soul(),
            user_preferences=self.load_user_preferences()
        )
        self.messages = [{
            "role": "system",
            "content": self.system_prompt
        }]
    
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

class OpenRouterAgent(Agent):
    def __init__(self, queue, telegram):
        super().__init__(queue, telegram)
        self.openrouter = OpenRouterClient(global_settings)
        self.model = global_settings.openrouter_model
        self.tool_definitions = tools_hub.get_tool_definitions_openai_style()
    
    def complete(self):
        response = self.openrouter.complete(
            self.model, 
            messages=self.messages, 
            tools=self.tool_definitions)
        return response
    
    def process_response(self, response):
        has_tool_calls = False
        for chunk in response['output']:
            if chunk['type'] == 'reasoning':
                for summary in chunk['summary']:
                    print(f"[white]Model Reasoning:\n{summary['text']}[/white]\n")
            elif chunk['type'] == 'message':
                self.messages.append(chunk)
                for content in chunk['content']:
                    print(f"[yellow]Model Response:\n{content['text']}[/yellow]\n")
                    self.telegram.send_telegram_msg(content['text'])
            elif chunk['type'] == 'function_call':
                self.messages.append(chunk)
                has_tool_calls = True
                id = chunk['id']
                call_id = chunk['call_id']
                call_name = chunk['name']
                call_args = json.loads(chunk['arguments'])
                print(f"[blue]Model Function Call:\nFunction Name: {call_name}\nFunction Arguments: {call_args}[/blue]\n")
                tool_result = tools_hub.run_tool(call_name, call_args)
                print(f"[green]Tool Result:\n{tool_result}[/green]\n")
                self.messages.append({
                    "type": "function_call_output",
                    "id": id + "_output",
                    "call_id": call_id,
                    "output": tool_result
                })
        return not has_tool_calls

class AnthropicAgent(Agent):
    def __init__(self, queue, telegram):
        super().__init__(queue, telegram)
        self.llm_client = anthropic.Anthropic(
            api_key=global_settings.anthropic_api_key,
            base_url=global_settings.anthropic_base_url
        )
        self.model = global_settings.anthropic_model
        self.system_prompt = SYSTEM_PROMPT + f'\nYour current working directory is: {global_settings.working_directory}'
        self.messages = []
        self.tool_definitions = tools_hub.get_tool_definitions_claude_style()
    
    def complete(self):
        message = self.llm_client.messages.create(
            model=self.model,
            max_tokens=1024,
            tools=self.tool_definitions,
            system=self.system_prompt,
            messages=self.messages
        )
        return message
    
    def process_response(self, message):
        self.messages.append({
            "role": "assistant",
            "content": message.content
        })

        tool_results = []
        has_output_text = False
        for block in message.content:
            if block.type == "thinking":
                print(f"[white]Thinking:\n{block.thinking}[/white]\n")
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id
                print(f"[blue]Tool Use:\nTool Name: {tool_name}\nTool Input: {tool_input}[/blue]\n")
                tool_result = tools_hub.run_tool(tool_name, tool_input)
                print(f"[green]Tool Result:\n{tool_result}[/green]\n")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": tool_result
                })
            elif block.type == "text":
                has_output_text = True
                print(f"[orange]Text:\n{block.text}[/orange]\n")
                self.telegram.send_telegram_msg(block.text)
        if len(tool_results) > 0:
            self.messages.append({
                "role": "user",
                "content": tool_results
            })
            return False
        if not has_output_text:
            return False
        return True

def main():
    global_settings.load()
    initalize.init()
    
    telegram = TelegramClient(global_settings)
    q = queue.Queue()

    def on_message(msg):
        q.put(msg)

    polling_thread = threading.Thread(target=telegram.polling, args=(on_message,), daemon=True)
    polling_thread.start()

    agent = None
    if global_settings.model_provider == "openrouter":
        agent = OpenRouterAgent(q, telegram)
    elif global_settings.model_provider == "anthropic":
        agent = AnthropicAgent(q, telegram)
    else:
        print(f"[red]Unsupported model provider: {global_settings.model_provider}[/red]")
        return

    if agent is not None:
        agent.loop()

if __name__ == "__main__":
    main()
