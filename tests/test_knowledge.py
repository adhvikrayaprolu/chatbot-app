from pathlib import Path

import pytest

from app import create_app
from gpt_handler import ProviderError
from knowledge import Knowledge
from storage import Conflict, NotFound, Store


class Tokens:
    def fingerprint(self):
        return "fake-tokenizer"

    def count(self, text):
        return len(text.split())

    def split(self, text, size=500, overlap=75):
        words = text.split()
        return [' '.join(words[i:i+size]) for i in range(0, len(words), size-overlap)]


class Models:
    embedding = 'fake'
    model = 'fake'

    def digest(self, name):
        return 'fake-digest'

    def embed(self, texts):
        return [[1.0, 0.5] for _ in texts]

    def generate(self, messages, schema=None):
        return {'text': 'A barrier synchronizes a block [p1-c0].', 'input_tokens': 10, 'output_tokens': 5}


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setenv('RETRIEVAL_BIN', str(Path(__file__).parents[1] / 'retrieval/target/debug/document-retrieval'))
    store = Store(str(tmp_path / 'chat.db'))
    k = Knowledge(store, tmp_path / 'documents', Models(), Tokens())
    source = tmp_path / 'source.md'
    source.write_text('A block barrier synchronizes threads inside one block. It cannot synchronize separate blocks.')
    did = k.import_file('alice', source, 'Original notes', synchronous=True, markdown=True)
    assert k.document('alice', did)['status'] == 'ready'
    yield k, did
    k.worker.shutdown(wait=True)


def test_private_index_provenance_and_search(corpus):
    k, did = corpus
    hits = k.search('alice', did, 'barrier')
    assert hits[0]['page'] == 1
    assert hits[0]['id'] == 'p1-c0'
    with pytest.raises(NotFound):
        k.search('bob', did, 'barrier')
    result = k.answer('alice', did, 'What is a barrier?')
    assert result['citations'][0]['id'] == 'p1-c0'
    assert result['model_calls'] == 1


def test_invalid_citation_and_missing_evidence(corpus):
    k, did = corpus
    k.models.generate = lambda *args: {'text': 'Unfounded [p999-c0]', 'input_tokens': 1, 'output_tokens': 1}
    with pytest.raises(ProviderError):
        k.answer('alice', did, 'barrier')
    assert k.answer('alice', did, 'unknown', evidence=[])['reply'].startswith('Insufficient evidence')


def test_stale_models_and_delete(corpus):
    k, did = corpus
    k.models.digest = lambda name: 'changed'
    with pytest.raises(Conflict):
        k.search('alice', did, 'barrier')
    k.delete('alice', did)
    assert not (k.directory / did).exists()
    with pytest.raises(NotFound):
        k.document('alice', did)


def test_document_api_ownership_and_existing_chat(corpus):
    k, did = corpus
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': k.store.path}, knowledge=k)
    client = app.test_client()
    token = client.get('/api/session').json['csrf']
    assert client.get(f'/api/documents/{did}').status_code == 404
    with client.session_transaction() as session:
        session['owner'] = 'alice'
    chat = client.post('/api/conversations', json={'title': 'Study'}, headers={'X-CSRF-Token': token}).json
    result = client.post('/chat', json={'conversation_id': chat['id'], 'message': 'barrier', 'document_id': did}, headers={'X-CSRF-Token': token})
    assert result.status_code == 200
    assert result.json['grounded']['citations']
    assert len(client.get('/api/conversations/' + chat['id']).json['messages']) == 2
    with k.store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM answer_metadata').fetchone()[0] == 1


def test_failed_ingestion_is_recoverable(tmp_path):
    k = Knowledge(Store(str(tmp_path / 'chat.db')), tmp_path / 'docs', Models(), Tokens())
    source = tmp_path / 'bad.pdf'
    source.write_bytes(b'not a PDF')
    did = k.import_file('alice', source, 'bad', synchronous=True)
    assert k.document('alice', did)['status'] == 'failed'
    assert not k.document('alice', did)['metadata'].get('fingerprint')
    k.worker.shutdown(wait=True)

