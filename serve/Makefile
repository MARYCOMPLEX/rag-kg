.PHONY: install up down api worker cli lint typecheck arch test test-cov clean

# === Setup ===
install:
	uv sync

# === Infrastructure ===
up:
	docker compose -f infra/docker-compose.yml up -d

up-full:
	docker compose -f infra/docker-compose.yml --profile full up -d

down:
	docker compose -f infra/docker-compose.yml --profile full down

# === Run ===
api:
	uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run arq apps.worker.main.WorkerSettings

cli:
	uv run python -m apps.cli.main

# === Quality Gates ===
lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run pyright

arch:
	@echo "tach check — skipped until tach is configured"

test:
	uv run pytest tests/ -x -q

test-cov:
	uv run pytest tests/ --cov=packages --cov-report=term-missing --cov-fail-under=80

# === Eval (M1+) ===
eval-quick:
	@echo "Eval not available until M1"

eval-full:
	@echo "Eval not available until M6"

# === Cleanup ===
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov
