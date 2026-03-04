import anthropic
import tools_hub
import json
import initalize
from rich import print
from prompts import SYSTEM_PROMPT
import global_settings

llm_client = anthropic.Anthropic(
    api_key=global_settings.anthropic_api_key,
    base_url=global_settings.anthropic_base_url
)
tools_definition = [tool['doc'] for tool in tools_hub.TOOLS.values()]

def loop():
    all_messages = []
    system_prompt = SYSTEM_PROMPT + f'\nYour current working directory is: {global_settings.working_directory}' if global_settings.working_directory else ''

    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        return
    all_messages.append({
        "role": "user",
        "content": [ { "type": "text", "text": user_input } ]
    })

    while True:
        message = llm_client.messages.create(
            model=global_settings.anthropic_model,
            max_tokens=1024,
            tools=tools_definition,
            system=system_prompt,
            messages=all_messages
        )
        all_messages.append({
            "role": "assistant",
            "content": message.content
        })

        tool_results = []
        for block in message.content:
            if block.type == "thinking":
                print(f"[white]Thinking:\n{block.thinking}[/white]\n")
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id
                print(f"[blue]Tool Use:\nTool Name: {tool_name}\nTool Input: {tool_input}[/blue]\n")
                tool_result = tools_hub.run_tool(tool_name, tool_input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": tool_result
                })
            elif block.type == "text":
                print(f"[orange]Text:\n{block.text}[/orange]\n")
            else:
                print(f"[red]Unknown block type '{block.type}' with content:\n{block}[/red]\n")

        if len(tool_results) > 0:
            all_messages.append({
                "role": "user",
                "content": tool_results
            })
            continue
        if not any(block.type == "text" for block in message.content):
            continue

        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            return
        all_messages.append({
            "role": "user",
            "content": [ { "type": "text", "text": user_input } ]
        })


if __name__ == "__main__":
    global_settings.load()
    initalize.init()
    loop()
