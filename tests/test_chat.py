from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APITimeoutError, RateLimitError

from app import create_app
from gpt_handler import OpenAIProvider, ProviderError
from storage import Store, Conflict


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.error = None

    def reply(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return 'reply to ' + messages[-1]['content']


@pytest.fixture
def setup(tmp_path):
    config = {'TESTING': True, 'SECRET_KEY': 'test-only-secret',
              'DATABASE': str(tmp_path / 'chat.sqlite3')}
    provider = FakeProvider()
    app = create_app(config, provider)
    return app, provider, config


def owner(app):
    client = app.test_client()
    csrf = client.get('/api/session').json['csrf']
    return client, {'X-CSRF-Token': csrf}


def new(client, headers):
    result = client.post('/api/conversations', json={'title': 'A chat'}, headers=headers)
    assert result.status_code == 201
    return result.json['id']


def send(client, headers, cid, message='Hello'):
    return client.post('/chat', json={'conversation_id': cid, 'message': message}, headers=headers)


def test_browsers_and_conversations_have_independent_context(setup):
    app, provider, _ = setup
    a, ah = owner(app)
    b, bh = owner(app)
    a1, a2, b1 = new(a, ah), new(a, ah), new(b, bh)
    assert send(a, ah, a1, 'a1 private').status_code == 200
    assert send(a, ah, a2, 'a2 private').status_code == 200
    assert send(b, bh, b1, 'b private').status_code == 200
    assert send(a, ah, a1, 'a1 next').status_code == 200
    assert [x['content'] for x in provider.calls[-1][1:]] == ['a1 private', 'reply to a1 private', 'a1 next']
    assert len(b.get('/api/conversations').json['conversations']) == 1
    for path, method in [(f'/api/conversations/{a1}', 'get'),
                         (f'/api/conversations/{a1}', 'patch'),
                         (f'/api/conversations/{a1}', 'delete')]:
        response = getattr(b, method)(path, json={'title': 'Hijack'}, headers=bh)
        assert response.status_code == 404
    assert send(b, bh, a1).status_code == 404


def test_history_survives_restart_and_delete_cascades(setup):
    app, provider, config = setup
    client, headers = owner(app)
    cid = new(client, headers)
    send(client, headers, cid)
    cookie = client.get_cookie('session')
    restarted = create_app(config, provider).test_client()
    restarted.set_cookie('session', cookie.value)
    assert len(restarted.get(f'/api/conversations/{cid}').json['messages']) == 2
    renamed = restarted.patch(f'/api/conversations/{cid}', json={'title': 'Renamed'}, headers=headers)
    assert renamed.json['title'] == 'Renamed'
    assert restarted.delete(f'/api/conversations/{cid}', headers=headers).status_code == 204
    assert restarted.get(f'/api/conversations/{cid}').status_code == 404
    with app.extensions['store'].connect() as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0


@pytest.mark.parametrize('payload', [None, [], {}, {'message': 1}, {'message': ''},
                                     {'message': ' '}, {'message': 'a'*2001}])
def test_invalid_messages_never_call_provider(setup, payload):
    app, provider, _ = setup
    client, headers = owner(app)
    cid = new(client, headers)
    if isinstance(payload, dict):
        payload['conversation_id'] = cid
    response = client.post('/chat', json=payload, headers=headers)
    assert response.status_code == 400
    assert not provider.calls


def test_csrf_and_body_size_boundaries(setup):
    app, _, _ = setup
    client, headers = owner(app)
    assert client.post('/api/conversations', json={'title': 'No token'}).status_code == 403
    assert client.post('/api/conversations', json={'title': 'x'*20000}, headers=headers).status_code == 413
    assert client.post('/api/conversations', json={'title': 'x'*81}, headers=headers).status_code == 400


@pytest.mark.parametrize('code', [429, 502, 503, 504])
def test_provider_failure_does_not_persist_partial_turn(setup, code):
    app, provider, _ = setup
    client, headers = owner(app)
    cid = new(client, headers)
    provider.error = ProviderError('Try again later.', code)
    assert send(client, headers, cid).status_code == code
    assert client.get(f'/api/conversations/{cid}').json['messages'] == []
    provider.error = None
    assert send(client, headers, cid).status_code == 200


def test_optimistic_conflict_preserves_complete_turns(tmp_path):
    store = Store(str(tmp_path / 'chat.db'))
    cid = store.create('owner', 'Title')['id']
    store.append_turn('owner', cid, 0, 'first', 'reply')
    with pytest.raises(Conflict):
        store.append_turn('owner', cid, 0, 'second', 'wrong')
    assert len(store.get('owner', cid)['messages']) == 2


def test_context_and_conversation_limits(setup):
    app, provider, _ = setup
    client, headers = owner(app)
    cid = new(client, headers)
    for i in range(12):
        assert send(client, headers, cid, str(i)).status_code == 200
    assert len(provider.calls[-1]) == 22  # system + last 20 messages + user
    for i in range(49):
        new(client, headers)
    assert client.post('/api/conversations', json={'title': 'Too many'}, headers=headers).status_code == 409


def test_provider_configuration_and_timeout_errors():
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        OpenAIProvider('', 'gpt-4.1-mini')
    provider = OpenAIProvider('test-not-a-real-key', 'gpt-4.1-mini')
    assert provider.client.max_retries == 0
    provider.client.chat.completions.create = Mock(side_effect=APITimeoutError(request=httpx.Request('POST', 'https://example.test')))
    with pytest.raises(ProviderError) as error:
        provider.reply([{'role': 'user', 'content': 'hello'}])
    assert error.value.status == 504
    provider.client.chat.completions.create = Mock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))]))
    assert provider.reply([{'role': 'user', 'content': 'hello'}]) == 'ok'


def test_security_headers_and_plain_text_ui(setup):
    app, _, _ = setup
    response = app.test_client().get('/')
    assert response.status_code == 200
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control'] == 'no-store'


def test_readiness_is_cookie_free_and_never_calls_provider(setup):
    app, provider, _ = setup
    provider.error = ProviderError('Unavailable provider')
    response = app.test_client().get('/healthz')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}
    assert 'Set-Cookie' not in response.headers
    assert not provider.calls


def test_readiness_reports_missing_schema_without_internal_details(setup):
    app, provider, _ = setup
    with app.extensions['store'].connect() as db:
        db.execute('DROP TABLE messages')
        db.execute('DROP TABLE conversations')
    response = app.test_client().get('/healthz')
    assert response.status_code == 503
    assert response.json == {'status': 'unavailable'}
    assert not provider.calls


def test_readiness_reports_unreachable_database(setup, tmp_path):
    app, provider, _ = setup
    app.extensions['store'].path = str(tmp_path / 'missing-directory' / 'chat.db')
    response = app.test_client().get('/healthz')
    assert response.status_code == 503
    assert response.json == {'status': 'unavailable'}
    assert not provider.calls
