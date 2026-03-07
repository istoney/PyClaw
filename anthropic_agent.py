import json
import tools_hub
import global_settings
import anthropic
from agent import Agent
from rich import print
from prompts import COMPRESS_PROMPT, TASK_COMPLETION_CHECK_PROMPT

class AnthropicAgent(Agent):

    def __init__(self, queue, telegram):
        super().__init__(queue, telegram)
        self.llm_client = anthropic.Anthropic(
            api_key=global_settings.anthropic_api_key,
            base_url=global_settings.anthropic_base_url
        )
        self.model = global_settings.anthropic_model
        self.tool_definitions = tools_hub.get_tool_definitions_claude_style()
        self.messages = []
    
    def generate(self, model, messages, tools=None):
        message = self.llm_client.messages.create(
            model=model,
            messages=messages,
            system=self.system_prompt,
            tools=tools
        )
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        print(f"[purple]Generate, Input Tokens: {input_tokens}, Output Tokens: {output_tokens}[/purple]")
        return message, input_tokens, output_tokens
    
    def compress_conversation(self):
        conversation = json.dumps(self.messages)
        prompt = COMPRESS_PROMPT + "\n```\n" + conversation + "\n```\nNow start to summarize the conversation"
        message, input_tokens, output_tokens = self.generate(self.model, messages=[{
            "role": "system", 
            "content": prompt 
        }])

        compressed_summary = ""
        for block in message.content:
            if block.type == "text":
                compressed_summary += block.text + "\n"
        print(f"[purple]Compression Result (Output Tokens: {output_tokens}) [/purple]")
        print(f"[purple]{compressed_summary}[/purple]")

        self.messages = [{
            "role": "system",
            "content": f"Current conversation is:\n{compressed_summary}"
        }]
    
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
            return True
        return False
    
    def check_task_completion(self):
        messages = self.messages.copy()
        messages.append({
            "role": "system",
            "content": TASK_COMPLETION_CHECK_PROMPT
        })
        message, _, _ = self.generate(self.model, messages)
        for block in message.content:
            if block.type == "text":
                content = block.text
                data = json.loads(content)
                return data.get("task_done", False), data.get("reason", "")
        return False, ""
