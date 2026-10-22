"""Model gateway for ordinary chat. Providers are stateless and stream text deltas."""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

SYSTEM_PROMPT = 'You are a helpful assistant. Answer clearly and accurately. Use Markdown for code and lists.'


class ProviderError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class DemoProvider:
    """Deterministic offline replies so the app, tests and CI run without any model."""
    name = 'demo'

    def stream(self, messages) -> Iterator[str]:
        text = ('Offline demo mode — set `CHAT_PROVIDER=ollama` or `openai` for real answers. '
                'You said: ' + messages[-1]['content'])
        for word in text.split(' '):
            yield word + ' '

    def reply(self, messages) -> str:
        return ''.join(self.stream(messages)).strip()


class OllamaProvider:
    """Local models through Ollama's streaming chat API; never leaves the machine."""
    name = 'ollama'

    def __init__(self, host: str, model: str):
        self.host, self.model = host.rstrip('/'), model

    def stream(self, messages) -> Iterator[str]:
        body = {'model': self.model, 'messages': messages, 'stream': True, 'think': False,
                'options': {'temperature': 0.2, 'num_ctx': 8192}}
        try:
            with httpx.Client(timeout=180, trust_env=False) as client, \
                    client.stream('POST', self.host + '/api/chat', json=body) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        delta = json.loads(line).get('message', {}).get('content', '')
                        if delta:
                            yield delta
        except httpx.HTTPError as error:
            raise ProviderError('Local model unavailable. Start Ollama and pull the configured model.', 503) from error

    def reply(self, messages) -> str:
        return ''.join(self.stream(messages))


class OpenAIProvider:
    """Any OpenAI-compatible endpoint (OpenAI, vLLM, LM Studio) via OPENAI_BASE_URL."""
    name = 'openai'

    def __init__(self, api_key, model, base_url=None):
        if not api_key:
            raise ValueError('Set OPENAI_API_KEY or select CHAT_PROVIDER=demo.')
        self.client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=20, max_retries=0)
        self.model = model

    def _call(self, **kwargs):
        try:
            return self.client.chat.completions.create(model=self.model, max_completion_tokens=1000, **kwargs)
        except RateLimitError as error:
            raise ProviderError('The provider is busy. Try again later.', 429) from error
        except APITimeoutError as error:
            raise ProviderError('The provider timed out. Try again.', 504) from error
        except APIError as error:
            raise ProviderError('The provider is unavailable. Try again later.', 502) from error

    def stream(self, messages) -> Iterator[str]:
        try:
            for chunk in self._call(messages=messages, stream=True):
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except APIError as error:
            raise ProviderError('The provider stream was interrupted. Try again.', 502) from error

    def reply(self, messages) -> str:
        text = self._call(messages=messages).choices[0].message.content
        if not text:
            raise ProviderError('The provider returned an empty reply. Try again.', 502)
        return text


def create_provider(config) -> DemoProvider | OllamaProvider | OpenAIProvider:
    mode = config['CHAT_PROVIDER']
    if mode == 'demo':
        return DemoProvider()
    if mode == 'ollama':
        return OllamaProvider(config['OLLAMA_HOST'], config['LOCAL_CHAT_MODEL'])
    if mode == 'openai':
        return OpenAIProvider(config['OPENAI_API_KEY'], config['OPENAI_MODEL'], config['OPENAI_BASE_URL'])
    raise ValueError('CHAT_PROVIDER must be demo, ollama or openai.')
