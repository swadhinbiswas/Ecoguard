.PHONY: help install test lint format typecheck coverage clean run migrate check sync

help:
	@echo "Eco-Guard - LLM MLOps Platform"
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
