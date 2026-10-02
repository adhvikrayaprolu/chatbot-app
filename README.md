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

## Study methods and comparisons (milestone 2)

Use **Try original GPU notes**, wait for `ready`, and ask “Can a block barrier synchronize
separate blocks?” Select Standard RAG, Agentic RAG, or OKF navigation. Citation buttons
open the source passage and its PDF/printed-page provenance. **Compare methods** runs
three separate experiments and shows time, input/output tokens, model calls and tool steps;
it never adds comparison answers to the conversation. Execution steps contain tool activity,
not hidden model reasoning. Imported PDFs and experiment details remain local.

LangChain adapts Ollama; LangGraph explicitly controls query → retrieve → assess transitions.
The agent gets at most two retrieval rounds (four decision calls plus one answer call).
OKF is a portable Markdown knowledge format, not a model or a guarantee of better answers.
This implementation builds lossless, source-backed concepts and linked page-range indexes,
then navigates root → passage with at most two hops and three model calls. It uses no vector
search. Bundles declare OKF v0.2, generated provenance and `draft` status; no human verification
is claimed. All three methods share the same answer instructions and 3,072-token evidence
budget. The final generator uses qwen3:4b, thinking disabled, temperature 0, 8,192 context,
and at most 1,024 output tokens. Model and tokenizer digests are recorded for evaluation.

Offline browser verification:
```sh
.venv/bin/pip install -r requirements-browser.txt
.venv/bin/python -m playwright install chromium
RUN_BROWSER=1 .venv/bin/python -m pytest -q tests/test_browser.py
```
The browser test runs real Flask, SQLite and Rust with deterministic fake model responses.
It needs neither Ollama nor the textbook. CI runs it separately from native/API/container checks.

## Optional local Langfuse

The app works without tracing. To use the separate development observability stack:
```sh
.venv/bin/python scripts/setup_observability.py
docker compose -p chatbot-local-observability --env-file instance/langfuse.env -f compose.langfuse.yaml up -d
set -a
. instance/langfuse.env
set +a
LANGFUSE_ENABLED=true make dev
```
Open http://localhost:3000. The generated ignored file contains the local developer login
(`study@localhost.test`) and private password. All services except the loopback-bound UI
are internal. S3Mock is a development object store; this configuration is for local experiments.
Spans capture numeric operational metadata and omit model inputs, outputs, arguments and
source content. Cloud endpoints are rejected and LangSmith tracing is disabled explicitly.
Stop the stack with the same Compose command and `down`; omit `--volumes` to retain its data.
