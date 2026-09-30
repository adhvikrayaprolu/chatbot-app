.PHONY: setup dev test
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	@test -f .env || cp .env.example .env
dev:
	.venv/bin/python app.py
test:
	.venv/bin/python -m pytest -q
