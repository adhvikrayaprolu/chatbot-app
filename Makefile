.PHONY: setup dev test check retrieval models bench
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	@test -f .env || cp .env.example .env
	$(MAKE) retrieval
retrieval:
	cargo build --locked --release --manifest-path retrieval/Cargo.toml
models:
	.venv/bin/python scripts/setup_models.py
dev:
	.venv/bin/python app.py
test:
	cargo build --locked --manifest-path retrieval/Cargo.toml
	cargo test --locked --manifest-path retrieval/Cargo.toml
	.venv/bin/python -m pytest -q
check:
	.venv/bin/ruff check app.py storage.py gpt_handler.py knowledge.py strategies.py observability.py evaluation.py evaluation_external.py bench.py tests scripts
	.venv/bin/mypy --config-file pyproject.toml
	cargo fmt --check --manifest-path retrieval/Cargo.toml
	cargo clippy --locked --manifest-path retrieval/Cargo.toml -- -D warnings
bench:
	.venv/bin/python bench.py retrieval
	.venv/bin/python bench.py answers --split development
	.venv/bin/python bench.py report
