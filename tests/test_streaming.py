import json

import pytest

from app import create_app
from knowledge import AnswerField
from providers import DemoProvider, create_provider
from tests.test_chat import FakeProvider, new, owner
from tests.test_knowledge import corpus  # noqa: F401  (fixture)


def events(response):
    parsed = []
    for block in response.get_data(as_text=True).strip().split('\n\n'):
        name, data = block.split('\n', 1)
        parsed.append((name.removeprefix('event: '), json.loads(data.removeprefix('data: '))))
    return parsed


class StreamingProvider(FakeProvider):
    def stream(self, messages):
        self.calls.append(messages)
        yield from ('Hello ', 'there')


def test_ordinary_chat_streams_tokens_then_saves_turn(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(tmp_path / 'c.db')}, StreamingProvider())
    client, headers = owner(app)
    cid = new(client, headers)
    response = client.post(f'/api/conversations/{cid}/messages', json={'message': 'Hi'}, headers=headers)
    assert response.mimetype == 'text/event-stream'
    received = events(response)
    assert [e for e, _ in received] == ['token', 'token', 'done']
    assert received[-1][1]['reply'] == 'Hello there'
    saved = client.get(f'/api/conversations/{cid}').json['messages']
    assert [m['content'] for m in saved] == ['Hi', 'Hello there']


def test_stream_rejects_foreign_conversation_before_opening(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(tmp_path / 'c.db')}, StreamingProvider())
    alice, alice_headers = owner(app)
    bob, bob_headers = owner(app)
    cid = new(alice, alice_headers)
    response = bob.post(f'/api/conversations/{cid}/messages', json={'message': 'Hi'}, headers=bob_headers)
    assert response.status_code == 404


def test_grounded_stream_reports_steps_evidence_and_citations(corpus, tmp_path):  # noqa: F811
    k, _ = corpus
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': k.store.path}, StreamingProvider(), knowledge=k)
    client, headers = owner(app)
    did = client.post('/api/documents/demo', headers=headers).json['id']
    k.jobs[did].result()
    cid = new(client, headers)
    response = client.post(f'/api/conversations/{cid}/messages',
                           json={'message': 'What is a barrier?', 'document_id': did, 'method': 'rag'}, headers=headers)
    received = events(response)
    names = [e for e, _ in received]
    assert names[0] == 'step' and 'evidence' in names and names[-1] == 'done'
    done = received[-1][1]
    assert done['grounded']['citations'][0]['id'] == 'p1-c0'
    failed = client.post(f'/api/conversations/{cid}/messages',
                         json={'message': 'x', 'document_id': did, 'method': 'nope'}, headers=headers)
    assert events(failed)[-1] == ('error', {'error': 'Unknown answering method.'})


def test_answer_field_decodes_partial_json_incrementally():
    field = AnswerField()
    raw = '{"answer": "Tiles \\"fit\\" in\\nshared'
    assert field.feed(raw[:10]) == ''
    assert field.feed(raw) == 'Tiles "fit" in\nshared'
    assert field.feed(raw + ' memory [p1-c0]", "citations": ["p1-c0"]}') == ' memory [p1-c0]'


def test_provider_gateway_configuration():
    assert ''.join(DemoProvider().stream([{'role': 'user', 'content': 'ping'}])).strip().endswith('ping')
    base = {'OLLAMA_HOST': 'http://127.0.0.1:11434', 'LOCAL_CHAT_MODEL': 'qwen3:4b',
            'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'm', 'OPENAI_BASE_URL': None}
    assert create_provider({**base, 'CHAT_PROVIDER': 'ollama'}).name == 'ollama'
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        create_provider({**base, 'CHAT_PROVIDER': 'openai'})
    with pytest.raises(ValueError, match='CHAT_PROVIDER'):
        create_provider({**base, 'CHAT_PROVIDER': 'gpt'})
