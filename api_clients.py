import json
from abc import ABC, abstractmethod
import openai
import anthropic

class APIClient(ABC):
    @abstractmethod
    def create_chat_completion(self, messages, temperature=0.0):
        pass

class OpenAIClient(APIClient):
    def __init__(self, model):
        self.client = openai.OpenAI()
        self.model = model

    def create_chat_completion(self, messages, temperature=0.0):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature
        )
        return json.loads(response.choices[0].message.content)

class AnthropicClient(APIClient):
    def __init__(self, model):
        self.client = anthropic.Anthropic()
        self.model = model

    def create_chat_completion(self, messages, temperature=0.0):
        prompt = "\n\n".join([f"{m['role']}: {m['content']}" for m in messages])
        response = self.client.completions.create(
            model=self.model,
            prompt=prompt,
            max_tokens_to_sample=1000,
            temperature=temperature
        )
        return json.loads(response.completion)