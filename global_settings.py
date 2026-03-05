import json
from rich import print

working_directory = "~"
telegram_bot_token = None
telegram_chat_id = None
http_proxy = None
https_proxy = None
gemini_api_key = None
openrouter_model = None
openrouter_api_key = None
anthropic_base_url = None
anthropic_api_key = None
anthropic_model = None
model_provider = None
compression_threshold = 3000

def load():
    with open("settings.json", "r") as f:
        settings = json.load(f)
        global working_directory, telegram_bot_token, telegram_chat_id, http_proxy, https_proxy
        global openrouter_model, openrouter_api_key
        global anthropic_base_url, anthropic_api_key, anthropic_model
        global gemini_api_key
        global model_provider
        global compression_threshold
        working_directory = settings.get("working_directory", working_directory)
        telegram_bot_token = settings.get("telegram_bot_token", telegram_bot_token)
        telegram_chat_id = settings.get("telegram_chat_id", telegram_chat_id)
        http_proxy = settings.get("http_proxy", http_proxy)
        https_proxy = settings.get("https_proxy", https_proxy)
        openrouter_model = settings.get("openrouter_model", openrouter_model)
        openrouter_api_key = settings.get("openrouter_api_key", openrouter_api_key)
        anthropic_base_url = settings.get("anthropic_base_url", anthropic_base_url)
        anthropic_api_key = settings.get("anthropic_api_key", anthropic_api_key)
        anthropic_model = settings.get("anthropic_model", anthropic_model)
        gemini_api_key = settings.get("gemini_api_key", gemini_api_key)
        model_provider = settings.get("model_provider", model_provider)
        compression_threshold = settings.get("compression_threshold", compression_threshold)
        return
    print("[red]Failed to load settings.json. Please ensure the file exists and is properly formatted.[/red]")
