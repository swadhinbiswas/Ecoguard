# Installation

## Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20+ |
| Database | SQLite (built-in) | PostgreSQL 15 |
| RAM | 2 GB | 8+ GB |
| Disk | 1 GB | 10+ GB (for models) |

## Install uv Package Manager

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Install Project Dependencies

```bash
git clone git@github.com:swadhinbiswas/Ecoguard.git
cd Ecoguard

# Production dependencies only
uv sync

# Development dependencies (tests, linting, type checking)
uv sync --group dev
```

## Install Frontend Dependencies (Optional)

```bash
cd frontend
npm install
npm run build    # builds to frontend/dist/
cd ..
```

The built frontend is auto-served by FastAPI when `frontend/dist/` exists.

## Verify Installation

```bash
uv run python -c "from src.core.config import settings; print(settings.app_name)"
# Output: Eco-Guard

uv run pytest tests/ -q
# Output: 85 passed
```
