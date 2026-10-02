"""Opt-in loopback-only Langfuse spans. Never captures arguments or source text."""
from __future__ import annotations

import os
from functools import lru_cache, wraps
from typing import Any
from urllib.parse import urlparse


def mask(*, data: Any, **kwargs: dict[str, Any]) -> Any:
    return '[content omitted]'


@lru_cache(maxsize=1)
def client():
    if os.getenv('LANGFUSE_ENABLED', 'false').lower() != 'true':
        return None
    url = os.getenv('LANGFUSE_BASE_URL', 'http://127.0.0.1:3000')
    if urlparse(url).hostname not in ('localhost', '127.0.0.1', '::1', 'host.docker.internal'):
        raise ValueError('Private corpus traces require a local Langfuse endpoint.')
    from langfuse import Langfuse
    return Langfuse(base_url=url, public_key=os.getenv('LANGFUSE_PUBLIC_KEY'),
                    secret_key=os.getenv('LANGFUSE_SECRET_KEY'),
                    mask=mask, blocked_instrumentation_scopes=['langchain', 'langsmith'])


def traced(name: str, kind: str = 'span'):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            observer = client()
            if observer is None:
                return function(*args, **kwargs)
            with observer.start_as_current_observation(name=name, as_type=kind) as span:
                result = function(*args, **kwargs)
                if isinstance(result, dict):
                    metrics = {key: result[key] for key in ('seconds', 'input_tokens', 'output_tokens', 'model_calls', 'evidence_tokens') if key in result}
                    span.update(metadata=metrics)
                    result['trace_id'] = span.trace_id
                return result
        return run
    return decorate


def score(trace_id: str, name: str, value: float):
    observer = client()
    if observer:
        observer.create_score(trace_id=trace_id, name=name, value=value, data_type='NUMERIC')
