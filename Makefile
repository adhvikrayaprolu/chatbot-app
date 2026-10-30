.PHONY: setup dev test lock
setup:
	python3 -m venv .venv
	.venv/bin/pip install --require-hashes -r requirements-dev.txt
	.venv/bin/pip check
	@test -f .env || cp .env.example .env
dev:
	.venv/bin/python app.py
test:
	.venv/bin/python -m pytest -q

# Maintainer-only compiler; app startup and tests need only pip.
# LOCK_ARGS=--upgrade refreshes transitive pins within requirements.in bounds.
lock:
	python3 -m venv .lock-venv
	.lock-venv/bin/pip install uv==0.11.18
	.lock-venv/bin/uv pip compile requirements.in --universal --python-version 3.12 --generate-hashes --custom-compile-command 'make lock' $(LOCK_ARGS) --output-file requirements.txt
	.lock-venv/bin/uv pip compile requirements-dev.in --constraint requirements.txt --universal --python-version 3.12 --generate-hashes --custom-compile-command 'make lock' $(LOCK_ARGS) --output-file requirements-dev.txt
