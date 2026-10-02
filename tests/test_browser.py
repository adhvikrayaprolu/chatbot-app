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
    def generate(self, messages, schema=None, citation_ids=None):
        if schema:
            properties = schema['properties']
            if 'query' in properties:
                value = {'query': 'block barrier'}
            elif 'sufficient' in properties:
                value = {'sufficient': True}
            else:
                index = messages[-1]['content']
                value = {'ids': ['group-0' if 'Source indexes:' in index else 'p1-c0']}
            return {'text': json.dumps(value), 'input_tokens': 10, 'output_tokens': 5}
        return super().generate(messages)


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
        page.goto(browser_server)
        expect(page.locator('#send')).to_be_enabled()
        page.get_by_role('button', name='Try original GPU notes').click()
        expect(page.locator('#documentStatus')).to_contain_text('ready', timeout=15000)
        page.locator('#message').fill('What is a barrier?')
        page.locator('#message').press('Enter')
        expect(page.locator('#messages')).to_contain_text('A barrier synchronizes')
        page.get_by_role('button', name='p1-c0 · PDF page 1').click()
        expect(page.locator('#sourceDialog')).to_be_visible()
        expect(page.locator('#sourceText')).to_contain_text('GPU')
        page.keyboard.press('Escape')
        expect(page.locator('#sourceDialog')).not_to_be_visible()
        page.reload()
        expect(page.get_by_role('button', name='p1-c0 · PDF page 1')).to_be_visible()
        # Source selection is deliberately independent of persisted chat messages.
        page.locator('#document').select_option(index=1)
        page.locator('#message').fill('Does a barrier synchronize separate blocks?')
        page.get_by_role('button', name='Compare methods', exact=True).click()
        expect(page.locator('#comparisonDialog')).to_be_visible(timeout=15000)
        expect(page.locator('.comparisonCard')).to_have_count(3)
        expect(page.locator('#messages article')).to_have_count(2)
        page.keyboard.press('Escape')
        page.locator('#message').fill('Line one')
        page.locator('#message').press('Shift+Enter')
        expect(page.locator('#message')).to_have_value('Line one\n')
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button', name='Remove source', exact=True).click()
        page.get_by_role('button', name='Remove source', exact=True).last.click()
        expect(page.locator('#documentStatus')).to_contain_text('Ordinary conversation')
        bad = tmp_path / 'invalid.pdf'
        bad.write_bytes(b'invalid PDF')
        page.locator('#pdfFile').set_input_files(str(bad))
        page.get_by_role('button', name='Import PDF', exact=True).click()
        expect(page.locator('#documentStatus')).to_contain_text('failed', timeout=15000)
        expect(page.get_by_role('button', name='Retry import')).to_be_enabled()
        expect(page.locator('#send')).to_be_disabled()
        assert errors == []
        browser.close()
