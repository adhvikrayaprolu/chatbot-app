# Document Intelligence: agent guide

## Layout
- `app.py`: Flask API, CSRF, per-browser ownership, SSE message streaming.
- `knowledge.py`: PDF ingestion, grounded answering, citation validation, comparisons.
- `strategies.py`: agent (LangGraph), OKF navigation, scoped and rerank retrieval.
- `providers.py`: ordinary chat providers (demo / ollama / OpenAI-compatible).
- `storage.py`: owner-scoped SQLite for conversations.
- `retrieval/`: Rust search engine (JSON over stdin/stdout).
- `web/`: React + TypeScript + Vite client, built to `web/dist` and served by Flask.
- `bench.py`, `evaluation.py`, `evaluation_external.py`: benchmarks; `benchmarks/` holds aggregate results only.

## Commands
`make setup`, `make models`, `make dev`, `make web-dev`, `make test`, `make check`, `make bench`.
Browser end-to-end: `RUN_BROWSER=1 .venv/bin/python -m pytest tests/test_browser.py`.

## Rules
- Every document, conversation and comparison query is scoped to the owner; keep it that way and test the cross-owner path.
- Grounded answers must cite only supplied passage IDs or abstain. Don't weaken the schema or the post-validation.
- Imported PDFs, chunks, embeddings, OKF bundles, annotations and per-question answers stay in ignored `instance/`. Only aggregates go in `benchmarks/`.
- Document answering uses loopback Ollama only. Never send corpus text to a remote endpoint without an explicit opt-in.
- Tests use fake models and the debug Rust binary; never call paid APIs or the network from tests.
- A new answering method must share the generator, prompt and evidence budget, register in `knowledge.METHODS` and `strategies.STRATEGIES`, appear in `web/src/types.ts`, and get a benchmark entry in `bench.py`.
- Never commit secrets or `.env`. Work on a branch and open a PR; don't push to `main`.
