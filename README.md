# Persistent Chatbot
A Flask chatbot with private browser-owned conversations, durable history and an explicit offline demo.

## Overview
Create separate chats, switch between them and return to their history without mixing one conversation's context with another browser's data.

## Project Context
Originated in ClayHR internship work exploring HR-support chatbots. This public version focuses on conversation engineering; notebook/RAG experiments are not a shipped document-retrieval feature.

## Key Features
- Create, rename, switch and delete persistent conversations.
- SQLite ownership checks, bounded provider context and atomic successful turns.
- Safe plain-text rendering, pending/retry states and structured errors.
- Offline demo provider; optional OpenAI provider configured entirely through environment variables.

## Architecture / Tech Stack
Vanilla HTML/CSS/JavaScript → Flask app factory → owner-scoped SQLite store → injectable demo/OpenAI provider. Signed cookies identify a browser; CSRF protects writes. This is local browser ownership, not multi-device account authentication.

## Quick Start
Recommended: Docker with Compose v2 and a running Docker engine. No Python installation or API key is needed for the offline demo.
```sh
git clone https://github.com/adhvikrayaprolu/chatbot-app.git
cd chatbot-app
cp .env.example .env
docker compose up --build --wait --wait-timeout 90
```
Open http://127.0.0.1:5000. Startup waits for the HTTP/SQLite readiness check; provider availability is deliberately excluded. Use `docker compose logs -f` to inspect startup errors. If port 5000 is busy, change `CHAT_PORT` in `.env` and use that port in your browser.

`docker compose down` stops the app while retaining history and the session key in the `chat-data` volume. **`docker compose down --volumes` deletes that project's conversations and browser ownership key.** Source changes require rerunning the startup command to rebuild.

For native development instead, use Python 3.12/3.13 and Make: run `make setup` once, then `make dev`. Data and the session key live under ignored `instance/`. Dependencies pin direct versions; transitive versions are resolved by pip.

## Validation / Tests
```sh
make test
```
Run `make setup` first for the native test environment. Tests cover cross-browser isolation, persistence, CSRF, malformed requests, conflicts, provider failures and readiness without paid API calls. PR CI runs tests, validates Compose, waits for the built service to become healthy, and checks HTTP CRUD, browser isolation and persistence across a container restart in a disposable named volume.

## Environment Variables
`.env.example` documents `CHAT_PROVIDER=demo|openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`, optional `SECRET_KEY` and `COOKIE_SECURE`. Never edit a key into Python or commit `.env`. Hosted HTTPS use requires secure cookies and a private stable secret.

## Project Structure
`app.py`: API/factory; `storage.py`: persistence and ownership; `gpt_handler.py`: providers; `templates/` and `static/`: UI; `tests/`: API regressions.

## Current Status / Limitations
OpenAI credential-backed behavior requires owner verification. Public hosting also needs account authentication and abuse controls. A historical notebook credential-shaped string requires owner review; deleting current source cannot revoke it. The Compose demo is local-only; it does not provide production account authentication or verify live provider credentials.

See [AGENTS.md](AGENTS.md) for issue-based development and the readiness tracker in GitHub Issues for remaining work.
