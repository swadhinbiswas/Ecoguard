# Contributing to Eco-Guard

First off, thank you for considering contributing.

## Development Setup

```bash
git clone https://github.com/swadhinbiswas/Ecoguard.git
cd Ecoguard
uv sync --group dev
```

## Development Workflow

1. Fork the repository and create a branch from `main`
2. Install dependencies with `uv sync --group dev`
3. Make your changes with appropriate tests
4. Run `make check` to verify lint, format, type checking, and tests all pass
5. Submit a pull request

## Before Submitting

- All new features must include tests
- Code must pass `ruff format --check` and `ruff check`
- Type annotations are required for all public functions
- Database schema changes must include an Alembic migration
- Frontend changes must be tested in the Vue SPA build

## Pull Request Process

1. Update the README if your change adds a feature or changes behavior
2. Add yourself to the contributors list if desired
3. The PR will be merged once it receives approval and CI passes
4. Maintainers may request changes before merging

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration is in `pyproject.toml`.

```bash
make format   # Auto-format all code
make lint     # Check for issues
make check    # Full CI check (lint + typecheck + tests)
```

## Project Structure

See the [README.md](README.md#project-structure) for a complete directory layout.

## Questions?

Open a GitHub Discussion or email the maintainers.
