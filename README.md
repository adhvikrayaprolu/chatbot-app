# Conversation notebook

A small Flask chatbot that keeps separate, persistent conversations for each browser and makes provider failures recoverable.

## Demo

The default offline demo echoes a message without an API key or paid requests. Start the app, create two conversations, send a message in each, and reload: each history remains separate. Use a second browser profile to verify ownership isolation. No screenshot is claimed until a browser run is verified.

## What it does

Create, rename, switch and delete chats; retain their messages in SQLite; send the last ten turns to the configured provider. Keyboard controls and responsive native HTML keep the interface simple. Text is displayed as plain text to avoid executing user/model HTML.

## Architecture / tech stack

Browser → Flask JSON routes → SQLite Store + stateless OpenAI provider. Flask signed HttpOnly SameSite cookies identify a random browser owner; messages stay server-side. `storage.py` includes owner in every query and commits complete turns atomically. Optimistic version checks reject concurrent replies rather than mixing history. No global conversation list.

## Quick start

Python 3.11+ and Make:

```sh
cp .env.example .env
make setup
make dev
```

Open http://127.0.0.1:5000. `make dev` is the preferred local run command. Port 5000 conflicts on some macOS configurations; stop the conflicting local service or use `.venv/bin/flask --app 'app:create_app()' run --port 5001`.

Optional Docker path:

```sh
cp .env.example .env
docker compose up --build
```

Compose binds localhost and retains SQLite in `chat-data`. `docker compose down` keeps history; `down -v` deletes it. Docker build/runtime verification may require a running Docker daemon.

## Configuration

`CHAT_PROVIDER=demo` is explicit offline mode. Set `CHAT_PROVIDER=openai` and `OPENAI_API_KEY` in `.env` for real replies; keep the original `gpt-4.1-mini` model or set `OPENAI_MODEL`. Credentials never belong in source. Missing keys/unknown providers fail at startup. Provider requests time out after 20 seconds with retries disabled, and errors return meaningful HTTP statuses without leaking provider responses.

SQLite defaults to `instance/chat.sqlite3`; override `CHAT_DATABASE`. A local session signing key is generated once in ignored `instance/session.key`. Keep it stable with the database. HTTPS deployments require a strong `SECRET_KEY` and `COOKIE_SECURE=true`.

## Testing

```sh
make test
```

Tests use an injected fake provider and temporary database; no network or key required. CI runs tests/Python startup compilation and a Docker build with read-only repository permissions.

## Project structure / API

- `app.py`: factory, validation, CSRF and conversation routes.
- `storage.py`: SQLite ownership/persistence and concurrent-turn checks.
- `gpt_handler.py`: stateless provider/error translation.
- `static/`, `templates/`: responsive plain-text UI.
- `tests/`: isolation, persistence, failures and input boundaries.
- `notebooks/`: historical experiments, not runtime features.

GET `/api/session` returns a CSRF token. GET/POST `/api/conversations`, GET/PATCH/DELETE `/api/conversations/<id>` manage owned chats. POST `/chat` takes `conversation_id` and `message`; mutations require `X-CSRF-Token`. Limits: 2,000 characters per prompt, 50 conversations per browser, 100 turns per conversation, last ten turns supplied as context.

## Design decisions / known limitations

Cookie ownership suits a local demo, not account authentication. Clearing cookies loses access to old chats; no account sync/import is implemented. Old localStorage-only histories are not imported. SQLite data is plaintext on local disk. Anyone sharing the same browser profile shares access. Public hosting needs real authentication, abuse/rate controls, retention policy and HTTPS; do not expose this localhost demo as a public service. Markdown rendering, streaming and document upload are deliberately absent from the application.

## Credential exposure follow-up

The original `notebooks/chatbot_intro.ipynb` contained a credential-shaped OpenAI key. Its validity is unknown; current source/output was redacted. A human should revoke that key if real and review repository history/account usage. This change does not remove it from old Git commits and does not rotate credentials.

## Future work

Only documented baseline gaps: browser interaction automation and human-verified demo screenshots, then authenticated hosting if this becomes a deployed product.
