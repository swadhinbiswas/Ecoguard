.PHONY: help install test lint format typecheck coverage clean run migrate check sync cli guardrails cost chat seed analytics finetune backup compare digest bench settings

help:
	@echo "Eco-Guard — LLM Inference Gateway + MLOps Platform"
	@echo ""
	@echo "Usage:"
	@echo "  make sync          Sync dependencies with uv"
	@echo "  make install       Install all deps (sync + dev)"
	@echo "  make run           Run the development server"
	@echo "  make test          Run tests"
	@echo "  make coverage      Run tests with coverage report"
	@echo "  make lint          Run linters (ruff)"
	@echo "  make format        Format code with ruff"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make check         Run full CI check (lint + typecheck + test)"
	@echo "  make migrate       Run database migrations"
	@echo "  make cli           Run the Eco-Guard CLI"
	@echo "  make guardrails    Check a prompt against guardrails"
	@echo "  make cost          View 24h cost usage"
	@echo "  make chat          Chat with default model"
	@echo "  make seed          Generate demo seed data"
	@echo "  make analytics     View analytics summary"
	@echo "  make finetune      Start a fine-tuning job"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-up     Start services with docker-compose"
	@echo "  make docker-down   Stop docker-compose services"
	@echo "  make clean         Remove build artifacts"

sync:
	uv sync

install:
	uv sync --group dev

run:
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest tests/ -v

coverage:
	uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/ --ignore-missing-imports

check: lint typecheck test

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(m)"

cli:
	@if [ -z "$(c)" ]; then \
		uv run python sdk/cli.py --help; \
	else \
		uv run python sdk/cli.py $(c); \
	fi

chat:
	uv run python sdk/cli.py chat "$(p)" --stream

guardrails:
	uv run python sdk/cli.py guardrails "$(p)"

cost:
	uv run python sdk/cli.py cost --hours $(or $(h),24)

seed:
	curl -X POST http://localhost:8000/api/v1/seed/generate

analytics:
	curl -s http://localhost:8000/api/v1/analytics/summary | python3 -m json.tool

finetune:
	curl -X POST http://localhost:8000/api/v1/finetune \
		-H "Content-Type: application/json" \
		-d '{"base_model":"$(or $(m),./models/tinyllama.gguf)","dataset_path":"$(or $(d),data/dataset.jsonl)","output_dir":"./models/finetuned","rank":8,"epochs":3,"learning_rate":0.0002}' | python3 -m json.tool

backup:
	curl -X POST http://localhost:8000/api/v1/backup | python3 -m json.tool

compare:
	uv run python sdk/cli.py compare "$(p)"

digest:
	curl -s http://localhost:8000/api/v1/digest | python3 -m json.tool

bench:
	curl -X POST http://localhost:8000/api/v1/benchmarks/run-all | python3 -m json.tool

settings:
	@echo "Open http://localhost:8000/dashboard#/settings in your browser"

docker-build:
	docker build -t eco-guard:latest .

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -exec rm -f {} +
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/
