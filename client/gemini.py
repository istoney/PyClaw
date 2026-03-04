from google import genai
from google.genai import types

class GeminiClient:
    def __init__(self, settings):
        api_key = settings.gemini_api_key
        http_proxy = settings.http_proxy

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                client_args={
                    "proxy": http_proxy
                }
            )
        )

    def generate(self, model, contents, enable_search=False):
        config=types.GenerateContentConfig()
        if enable_search:
            config.tools = [types.Tool(google_search=types.GoogleSearch())]

        # model="gemini-3-flash-preview"
        # gemini-2.5-flash
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config
        )
        return response.text
