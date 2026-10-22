"""Offline browser acceptance: real API/persistence/Rust, deterministic fake models."""
import json
import os
import threading
from pathlib import Path

import pytest

if os.getenv('RUN_BROWSER') != '1':
    pytest.skip('Set RUN_BROWSER=1 after installing requirements-browser.txt and Chromium.', allow_module_level=True)

from playwright.sync_api import expect, sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402
from knowledge import Knowledge  # noqa: E402
from storage import Store  # noqa: E402
from tests.test_knowledge import Models, Tokens  # noqa: E402


class BrowserModels(Models):
    def generate(self, messages, schema=None, citation_ids=None, on_token=None):
        if schema:
            properties = schema['properties']
            if 'query' in properties:
                value = {'query': 'block barrier'}
            elif 'sufficient' in properties:
                value = {'sufficient': True}
            else:
                value = {'ids': ['s0' if 'Table of contents:' in messages[-1]['content'] else 'p1-c0']}
            return {'text': json.dumps(value), 'input_tokens': 10, 'output_tokens': 5}
        return super().generate(messages, on_token=on_token)


@pytest.fixture
def browser_server(tmp_path, monkeypatch):
    monkeypatch.setenv('RETRIEVAL_BIN', str(Path(__file__).parents[1] / 'retrieval/target/debug/document-retrieval'))
    store = Store(str(tmp_path / 'study.db'))
    knowledge = Knowledge(store, tmp_path / 'documents', BrowserModels(), Tokens())
    app = create_app({'SECRET_KEY': 'offline-browser-test', 'DATABASE': store.path, 'CHAT_PROVIDER': 'demo'}, knowledge=knowledge)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    knowledge.worker.shutdown(wait=True)
    thread.join()


def test_study_flow_keyboard_comparison_and_mobile(browser_server, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: message.type == 'error' and errors.append(message.text))
        page.goto(browser_server)
        message = page.get_by_label('Message')
        # Ordinary chat streams from the offline provider.
        message.fill('Hello there')
        message.press('Enter')
        expect(page.locator('.message.assistant')).to_contain_text('You said: Hello there')
        expect(page.get_by_role('navigation', name='Saved conversations').get_by_role('button')).to_have_count(1)
        # Import the demo notes, ground the conversation and inspect a citation.
        page.get_by_role('button', name='Try GPU demo notes').click()
        expect(page.locator('.doc.ready')).to_have_count(1, timeout=15000)
        page.get_by_role('combobox').select_option(label='GPU Study Notes (original demo)')
        page.get_by_role('radio', name='Agent').click()
        message.fill('What is a barrier?')
        message.press('Enter')
        answer = page.locator('.message.assistant').last
        expect(answer).to_contain_text('A barrier synchronizes')
        expect(answer.locator('.trace summary')).to_contain_text('Agent')
        answer.get_by_role('button', name='Source 1: p1-c0').click()
        expect(page.get_by_role('complementary', name='Source passage')).to_contain_text('GPU')
        page.get_by_role('button', name='Close source').click()
        # Grounded metadata survives a reload.
        page.reload()
        expect(page.locator('.message.assistant').last.get_by_role('button', name='Source 1: p1-c0')).to_be_visible()
        # Comparisons run every method without touching the chat.
        message.fill('Does a barrier synchronize separate blocks?')
        page.get_by_role('button', name='Compare methods').click()
        expect(page.locator('.compare-card')).to_have_count(5, timeout=15000)
        expect(page.locator('.thread article')).to_have_count(4)
        page.keyboard.press('Escape')
        message.fill('Line one')
        message.press('Shift+Enter')
        expect(message).to_have_value('Line one\n')
        # Narrow screens: no horizontal overflow, menu reachable.
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button', name='Open menu').click()
        page.get_by_role('button', name='Remove GPU Study Notes (original demo)').click()
        page.get_by_role('button', name='Remove source', exact=True).click()
        expect(page.locator('.doc')).to_have_count(0)
        # A broken PDF fails visibly and offers retry.
        bad = tmp_path / 'invalid.pdf'
        bad.write_bytes(b'invalid PDF')
        page.locator('#pdf-file').set_input_files(str(bad))
        expect(page.locator('.doc.failed')).to_have_count(1, timeout=15000)
        expect(page.get_by_role('button', name='Retry')).to_be_visible()
        assert errors == []
        browser.close()
