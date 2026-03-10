import tools_hub
import global_settings
import json
from agent import Agent
from client.openrouter import OpenRouterClient
from rich import print
from prompts import COMPRESS_PROMPT, TASK_COMPLETION_CHECK_PROMPT

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
    
    def generate(self, model, messages, tools=[]):
        response = self.openrouter.complete(model, messages=messages, tools=tools)
        input_tokens = response['usage']['input_tokens']
        output_tokens = response['usage']['output_tokens']
        print(f"[purple]Generate Input Tokens: {input_tokens}, Output Tokens: {output_tokens}[/purple]")
        return response, input_tokens, output_tokens
    
    def generate_next_step(self):
        response, input_tokens, _ = self.generate(self.model, self.messages, tools=self.tool_definitions)
        return response, input_tokens
    
    def get_compress_messages(self):
        if len(self.messages) <= 4:
            return []

        call_id_map = set()
        i = -1
        while True:
            msg = self.messages[i]
            if msg['type'] == 'function_call_output':
                call_id_map.add(msg['call_id'])
            if msg['type'] == 'function_call':
                call_id_map.remove(msg['call_id'])
            if len(call_id_map) == 0 and i <= -4:
                break
            i -= 1

        return [self.messages[0]], self.messages[1:i], self.messages[i:]

    def compress_conversation(self):
        head, messages, tail = self.get_compress_messages()
        print(f"[purple]Compressing conversation. \n{len(head)}, {len(messages)}, {len(tail)}[/purple]")
        if not messages:            
            return  

        response, input_tokens, output_tokens = self.generate(self.model, messages=[{
            "role": "system",
            "content": f"{COMPRESS_PROMPT}\n```\n{json.dumps(messages)}\n```\nNow start to summarize the conversation"
        }])

        output_messages = [chunk for chunk in response['output'] if chunk['type'] == 'message']
        compressed_summary = output_messages[0]['content'][0]['text'] 
        print(f"[purple]Compression Result (Output Tokens: {output_tokens}) [/purple]")
        print(f"[purple]{compressed_summary}[/purple]")

        new_msg = {
            "role": "system",
            "content": f"Current conversation is:\n{compressed_summary}"
        }
        self.messages = head + [new_msg] + tail
    
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
        return has_tool_calls

    def check_task_completion(self):
        messages = self.messages.copy()
        messages.append({
            "role": "user",
            "content": TASK_COMPLETION_CHECK_PROMPT
        })
        response, _, _ = self.generate(self.model, messages)
        for chunk in response['output']:
            if chunk['type'] == 'message':
                content = chunk['content'][0]['text']
                print(f"[yellow]Task Completion Check Result:\n{content}[/yellow]\n")
                data = json.loads(content)
                return data.get("task_done", False), data.get("reason", "")
        return False, ""
