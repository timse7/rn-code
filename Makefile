PY   = python3
VENV = .venv
RUFF = $(shell [ -x $(VENV)/bin/ruff ] && echo $(VENV)/bin/ruff || echo ruff)

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "make venv    - create $(VENV) and install dependencies"
	@echo "make format  - auto-format sources and fix imports (ruff)"
	@echo "make lint    - run style and error checks (ruff)"
	@echo "make clean   - remove caches and build artifacts"

.PHONY: venv
venv:
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt -r requirements-dev.txt
	@echo "Run 'source $(VENV)/bin/activate' to activate."

.PHONY: format
format:
	@$(RUFF) format .
	@$(RUFF) check --fix .

.PHONY: lint
lint:
	@$(RUFF) check .

.PHONY: clean
clean:
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	@rm -rf .ruff_cache .mypy_cache .pytest_cache
	@echo "Cleaned."
