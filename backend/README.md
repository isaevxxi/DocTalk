# DokTalk Backend

FastAPI-based backend for the DokTalk ambient clinical scribe system.

## Setup

### Prerequisites
- Python 3.12+
- Poetry or uv
- PostgreSQL 16
- Redis 8.2.2+
- MinIO
- HashiCorp Vault

### Installation

```bash
# Install dependencies
poetry install

# Or with ML/ASR extras
poetry install --extras ml

# Activate virtual environment
poetry shell
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp ../.env.example .env
# Edit .env with your settings
```

### Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```

### Running

```bash
# Development server with auto-reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Testing

```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov

# Run only security/RLS tests
poetry run pytest -m security
poetry run pytest -m rls

# Run specific test file
poetry run pytest tests/unit/test_patients.py
```

### Code Quality

```bash
# Lint
poetry run ruff check .

# Format
poetry run black .

# Type check
poetry run mypy .

# All checks
poetry run ruff check . && poetry run black . && poetry run mypy .
```

## Project Structure

```
backend/
├── app/
│   ├── api/           # API endpoints
│   ├── core/          # Core config, security, logging
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── ml/            # ML/ASR pipeline
│   └── utils/         # Utilities
├── alembic/           # Database migrations
│   └── versions/      # Migration files
├── tests/
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── e2e/           # End-to-end tests
└── pyproject.toml     # Project config
```

## API Documentation

When running in development mode:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## Security & Compliance

See [Security Documentation](../docs/security/README.md) for:
- RLS (Row-Level Security) implementation
- Multi-tenancy isolation
- PII handling and sanitization
- Audit logging
- Compliance with 152-FZ, 323-FZ, Order 965n
