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
Python 3.13 and Make, from the repository root:
```sh
make setup
make dev
```
Open http://127.0.0.1:5000. Setup installs locked dependencies and creates `.env` only if missing. No API key is needed in demo mode. History and the local session key live under ignored `instance/`. Keep that directory to preserve browser ownership across restarts.

## Validation / Tests
```sh
make test
```
Tests cover cross-browser isolation, persistence, CSRF, malformed requests, conflict handling and provider failures without paid API calls. CI also builds the Docker image.

## Environment Variables
`.env.example` documents `CHAT_PROVIDER=demo|openai`, `OPENAI_API_KEY`, `OPENAI_MODEL`, optional `SECRET_KEY` and `COOKIE_SECURE`. Never edit a key into Python or commit `.env`. Hosted HTTPS use requires secure cookies and a private stable secret.

## Project Structure
`app.py`: API/factory; `storage.py`: persistence and ownership; `gpt_handler.py`: providers; `templates/` and `static/`: UI; `tests/`: API regressions.

## Current Status / Limitations
OpenAI credential-backed behavior requires owner verification. Public hosting also needs account authentication and abuse controls. A historical notebook credential-shaped string requires owner review; deleting current source cannot revoke it. Docker is an optional validation path, not the preferred startup workflow; local registry/runtime results are recorded in the integration PR.

See [AGENTS.md](AGENTS.md) for issue-based development and the readiness tracker in GitHub Issues for remaining work.

## Local document intelligence (milestone 1)

Grounded mode uses a Rust SQLite retrieval CLI (FTS5 + cosine + reciprocal-rank fusion),
Python PDF ingestion and local Ollama models. Ordinary conversation mode remains available.
Install Rust (minimal rustup profile) and Ollama, start `ollama serve`, then run
`make setup` and `make models`. Models download locally; no paid API key is needed.
`make test` exercises the native Rust engine and offline Python API tests; `make check`
runs lint, type checking, Rust format and clippy.

Import a PDF through `POST /api/documents` (multipart `file`, session CSRF header;
64 MiB limit), or use `POST /api/documents/demo` for the original GPU notes.
Poll `GET /api/documents/<id>`; imports report queued/indexing/ready/failed.
Add `document_id` and `method: "rag"` to the existing `/chat` JSON request.
Answers include citation IDs, PDF page provenance, model token usage and elapsed time.
Source inspection uses `/api/documents/<id>/sources/<passage-id>`.
Delete a document with DELETE or retry a failed/interrupted import with POST to `/retry`.
All document endpoints check browser ownership; this remains a local app, not hosted account authentication.

A single application process coordinates background ingestion (four HTTP threads in the image).
The Rust engine runs as a subprocess, not a network service. Index configuration and embedding
model digests are checked before search. Imports reuse completed embedding batches when retried.
Tokenization uses the downloaded Qwen tokenizer. Text extraction records empty/short pages;
figure-only answers are unsupported. Citation IDs are validated, but citation support and answer
correctness still require evaluation; valid IDs alone do not prove factual grounding.

The private textbook is user-supplied and **never included in Git, Docker build context or public traces**.
Private artifacts reside in ignored `instance/`. Do not remove this directory if you want to preserve
history, browser ownership, indexes or cached models/tokenizers. Source deletion removes the private
corpus and comparisons; already-saved conversation text remains until its conversation is deleted.
The original public fixture is independently written and safe to share.
