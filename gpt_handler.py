"""Stateless provider boundary. Never stores browser conversation state."""
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

SYSTEM_PROMPT = 'You are a helpful assistant. Answer clearly and accurately.'


class ProviderError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class DemoProvider:
    def reply(self, messages):
        return 'Offline demo reply: ' + messages[-1]['content']


class OpenAIProvider:
    def __init__(self, api_key, model):
        if not api_key:
            raise ValueError('Set OPENAI_API_KEY or select CHAT_PROVIDER=demo.')
        self.client = OpenAI(api_key=api_key, timeout=20, max_retries=0)
        self.model = model

    def reply(self, messages):
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_completion_tokens=1000)
            text = response.choices[0].message.content
            if not text:
                raise ProviderError('The provider returned an empty reply. Try again.', 502)
            return text
        except RateLimitError as error:
            raise ProviderError('The provider is busy. Try again later.', 429) from error
        except APITimeoutError as error:
            raise ProviderError('The provider timed out. Try again.', 504) from error
        except APIError as error:
            raise ProviderError('The provider is unavailable. Try again later.', 502) from error
