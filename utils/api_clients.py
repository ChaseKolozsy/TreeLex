import json
from abc import ABC, abstractmethod
import openai
import anthropic
import time

SLEEP_TIME = 1

class APIClient(ABC):
    @abstractmethod
    def create_chat_completion(self, messages, temperature=0.0):
        pass

class OpenAIClient(APIClient):
    def __init__(self, model):
        self.client = openai.OpenAI()
        self.model = model

    def create_chat_completion(self, messages, system=None, temperature=0.0, max_tokens=4096):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

class AnthropicClient(APIClient):
    def __init__(self, model):
        self.client = anthropic.Anthropic()
        self.model = model

    def create_chat_completion(self, messages, system, temperature=0.0, max_tokens=4096):
        response = self.client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        time.sleep(SLEEP_TIME)
        return response.content[0].text