import tools_hub
import global_settings
import json
from agent import Agent
from client.openrouter import OpenRouterClient
from rich import print
from prompts import COMPRESS_PROMPT

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
        self.tool_results = {}
    
    def generate_next_step(self):
        response = self.openrouter.complete(
            self.model, 
            messages=self.messages, 
            tools=self.tool_definitions)
        input_tokens = response['usage']['input_tokens']
        print(f"[purple]Generate Input Tokens: {input_tokens}[/purple]")
        return response, input_tokens
    
    def compress_conversation(self):
        conversation = json.dumps(self.messages[1:-1])
        prompt = COMPRESS_PROMPT + "\n```\n" + conversation + "\n```\nNow start to summarize the conversation"
        response = self.openrouter.complete(self.model, messages=[{
            "role": "system",
            "content": prompt
        }])

        output_tokens = response['usage']['output_tokens']
        compressed_summary = ""
        for chunk in response['output']:
            if chunk['type'] == 'message':
                for content in chunk['content']:
                    compressed_summary += content['text'] + "\n"
        print(f"[purple]Compression Result (Output Tokens: {output_tokens}) [/purple]")
        print(f"[purple]{compressed_summary}[/purple]")

        self.messages = [{
            "role": "system",
            "content": self.system_prompt
        }, {
            "role": "system",
            "content": f"Current conversation is:\n{compressed_summary}"
        }]
    
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
                self.tool_results[call_id] = tool_result
                print(f"[green]Tool Result:\n{tool_result}[/green]\n")
                self.messages.append({
                    "type": "function_call_output",
                    "id": id + "_output",
                    "call_id": call_id,
                    "output": tool_result
                })
        return not has_tool_calls