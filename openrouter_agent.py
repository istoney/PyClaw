import tools_hub
import global_settings
import json
from agent import Agent
from client.openrouter import OpenRouterClient
from rich import print

class OpenRouterAgent(Agent):

    def __init__(self, queue, telegram):
        super().__init__(queue, telegram)
        self.openrouter = OpenRouterClient(global_settings)
        self.model = global_settings.openrouter_model
        self.tool_definitions = tools_hub.get_tool_definitions_openai_style()
        self.messages = [{
            "role": "system",
            "content": self.system_prompt
        }]
    
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