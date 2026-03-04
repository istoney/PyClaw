import requests
import httpx
from rich import print
import time

class TelegramClient:
    def __init__(self, settings):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.http_proxy = settings.http_proxy
        self.proxies = {
            "http": settings.http_proxy,
            "https": settings.https_proxy
        }

    def send_telegram_msg(self, text):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=payload, proxies=self.proxies)
        return response.json()

    def polling(self, message_callback):
        offset = 0
        with httpx.Client(timeout=40.0, proxy=self.http_proxy) as client: 
            while True:
                try:
                    url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={offset}&timeout=30"
                    resp = client.get(url)
                    data = resp.json()
                    for update in data.get("result", []):
                        print(f"[hot_pink]收到消息: {update['message']['text']}[/hot_pink]")
                        message_callback(update['message']['text'])
                        offset = update["update_id"] + 1
                except Exception as e:
                    print(f"[red]错误: {e}[/red]")
                    time.sleep(3) 


