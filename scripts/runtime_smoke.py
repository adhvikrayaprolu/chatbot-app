"""Exercise the actual HTTP server; optional Docker restart verifies durable state."""
import argparse
import http.cookiejar
import json
import subprocess
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:5000')
parser.add_argument('--restart-container')
args = parser.parse_args()

def browser():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

first, second = browser(), browser()

def call(client, path, method='GET', body=None, csrf=None):
    headers = {'Content-Type': 'application/json'}
    if csrf:
        headers['X-CSRF-Token'] = csrf
    data = json.dumps(body).encode() if body is not None else None
    with client.open(urllib.request.Request(args.url + path, data=data, method=method, headers=headers), timeout=5) as response:
        payload = response.read()
        return response.status, json.loads(payload) if payload else None

def ready(client):
    for attempt in range(60):
        try:
            return call(client, '/api/session')[1]
        except (urllib.error.URLError, ConnectionError):
            time.sleep(.25)
    raise RuntimeError('Server did not become ready within 15 seconds')

csrf = ready(first)['csrf']
assert ready(second)['provider'] == 'demo', 'Smoke check requires the offline demo provider'
status, conversation = call(first, '/api/conversations', 'POST', {'title': 'Runtime smoke'}, csrf)
assert status == 201
cid = conversation['id']
status, reply = call(first, '/chat', 'POST', {'conversation_id': cid, 'message': 'A disposable persistence check'}, csrf)
assert status == 200 and reply['reply']
call(first, '/api/conversations/' + cid, 'PATCH', {'title': 'Renamed smoke'}, csrf)
try:
    call(second, '/api/conversations/' + cid)
    raise AssertionError('Second browser could read the first browser conversation')
except urllib.error.HTTPError as error:
    assert error.code == 404
if args.restart_container:
    subprocess.run(['docker', 'restart', args.restart_container], check=True)
    assert ready(first)['csrf'] == csrf
saved = call(first, '/api/conversations/' + cid)[1]
assert saved['title'] == 'Renamed smoke' and len(saved['messages']) == 2
assert call(first, '/api/conversations/' + cid, 'DELETE', csrf=csrf)[0] == 204
print('Runtime CRUD, owner isolation and completed-turn persistence passed' + (' across Docker restart.' if args.restart_container else '.'))
