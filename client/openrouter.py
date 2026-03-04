import json
import requests
from rich import print

class OpenRouterClient():

    def __init__(self, settings):
        self.api_key = settings.openrouter_api_key
        self.proxy_url = settings.http_proxy

    def complete(self, model, messages, tools):
        data = {
            "model": model,
            "input": messages,
            "tools": tools,
            "tool_choice": "auto"
        }
        proxies = {
            "http": self.proxy_url,
            "https": self.proxy_url
        }
        response = requests.post(
            url='https://openrouter.ai/api/v1/responses',
            headers={
                "Authorization": f"Bearer {self.api_key}",
                'Content-Type': 'application/json',
                # "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
                # "X-OpenRouter-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
            },
            json=data,
            proxies=proxies
        )
        if response.status_code != 200:
            print(f"[red]Error calling OpenRouter API: {response.status_code} {response.text}[/red]")
            return None
        return json.loads(response.text)
