"""Cookie-owned conversations for a local chatbot; no global message history."""
import os
import fcntl
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

from gpt_handler import DemoProvider, OpenAIProvider, ProviderError, SYSTEM_PROMPT
from storage import Store, NotFound, Conflict


def create_app(config=None, provider=None):
    load_dotenv(Path(__file__).parent / '.env')
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        DATABASE=os.getenv('CHAT_DATABASE', str(Path(app.instance_path) / 'chat.sqlite3')),
        CHAT_PROVIDER=os.getenv('CHAT_PROVIDER', 'demo'),
        OPENAI_API_KEY=os.getenv('OPENAI_API_KEY'),
        OPENAI_MODEL=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
    )
    if config:
        app.config.update(config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        # Stable local key across workers/restarts; never tracked or sent to browser.
        key_path = Path(app.instance_path) / 'session.key'
        with key_path.open('a+') as key_file:
            fcntl.flock(key_file, fcntl.LOCK_EX)
            os.chmod(key_path, 0o600)
            key_file.seek(0)
            key = key_file.read()
            if not key:
                key = secrets.token_hex(32)
                key_file.write(key)
                key_file.flush()
            app.config['SECRET_KEY'] = key
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    store = Store(app.config['DATABASE'])
    mode = app.config['CHAT_PROVIDER']
    if mode not in ('demo', 'openai'):
        raise ValueError('CHAT_PROVIDER must be demo or openai.')
    app.extensions['provider'] = provider or (DemoProvider() if mode == 'demo' else
        OpenAIProvider(app.config['OPENAI_API_KEY'], app.config['OPENAI_MODEL']))
    app.extensions['store'] = store

    @app.before_request
    def identify_owner():
        if 'owner' not in session:
            session['owner'] = secrets.token_hex(32)
            session['csrf'] = secrets.token_hex(32)
        if request.method in ('POST', 'PATCH', 'DELETE'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
                return jsonify(error='Refresh the page before changing conversations.'), 403

    @app.after_request
    def protect_response(response):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(NotFound)
    def missing(error):
        return jsonify(error='Conversation not found.'), 404

    @app.errorhandler(Conflict)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(ProviderError)
    def provider_error(error):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        # Avoid logging provider content, request text or credential-bearing exceptions.
        app.logger.error('Request failed: %s', type(error).__name__)
        return jsonify(error='Unable to complete the request. Try again.'), 500

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            from werkzeug.exceptions import BadRequest
            raise BadRequest('Expected a JSON object.')
        return data

    def text(data, field, limit):
        from werkzeug.exceptions import BadRequest
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise BadRequest(f'{field} must be nonempty text up to {limit} characters.')
        return value.strip()

    @app.get('/')
    def home():
        return render_template('index.html')

    @app.get('/api/session')
    def session_info():
        return jsonify(csrf=session['csrf'], provider=mode)

    @app.get('/api/conversations')
    def list_conversations():
        return jsonify(conversations=store.list(session['owner']))

    @app.post('/api/conversations')
    def create_conversation():
        data = payload()
        return jsonify(store.create(session['owner'], text(data, 'title', 80))), 201

    @app.get('/api/conversations/<cid>')
    def get_conversation(cid):
        return jsonify(store.get(session['owner'], cid))

    @app.patch('/api/conversations/<cid>')
    def rename_conversation(cid):
        return jsonify(store.rename(session['owner'], cid, text(payload(), 'title', 80)))

    @app.delete('/api/conversations/<cid>')
    def delete_conversation(cid):
        store.delete(session['owner'], cid)
        return '', 204

    @app.post('/chat')
    def chat():
        data = payload()
        message = text(data, 'message', 2000)
        cid = text(data, 'conversation_id', 64)
        conversation = store.get(session['owner'], cid)
        if len(conversation['messages']) >= 200:
            raise Conflict('This chat has reached 100 turns. Start a new conversation.')
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages += conversation['messages'][-20:]
        messages.append({'role': 'user', 'content': message})
        reply = app.extensions['provider'].reply(messages)
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 10000:
            raise ProviderError('The provider returned an invalid reply.', 502)
        store.append_turn(session['owner'], cid, conversation['version'], message, reply)
        return jsonify(reply=reply, conversation_id=cid)

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
