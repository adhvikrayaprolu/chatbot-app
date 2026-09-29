PYTHON ?= python3
.PHONY: check
check:
	$(PYTHON) -m py_compile app.py gpt_handler.py
	$(PYTHON) -c "import flask; import openai"
