import initalize
import threading
import queue
import global_settings
from client.telegram import TelegramClient
from openrouter_agent import OpenRouterAgent
from anthropic_agent import AnthropicAgent

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

    agent.loop()

if __name__ == "__main__":
    main()
