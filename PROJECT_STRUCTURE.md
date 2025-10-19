# DokTalk Project Structure

**Last Updated:** 2025-10-14
**Status:** Clean and organized ✓

---

## Root Directory

```
DocTalk/
├── README.md                    # Main project documentation
├── CONTRIBUTING.md              # Development guidelines
├── QUICKSTART.md               # Quick start guide for developers
├── .env.example                # Environment configuration template
├── .env                        # Local environment (git-ignored)
├── .gitignore                  # Git ignore rules
├── Makefile                    # Common development commands
├── docker-compose.minimal.yml  # Minimal dev setup (default)
├── docker-compose.yml          # Full production-like stack
└── PROJECT_STRUCTURE.md        # This file
```

---

## Backend (Python/FastAPI)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── worker.py               # Celery worker configuration
│   ├── api/                    # API endpoints (empty - to be built)
│   ├── core/
│   │   ├── config.py          # Application settings
│   │   └── logging.py         # Structured logging with PII sanitization
│   ├── models/                 # SQLAlchemy models (empty)
│   ├── schemas/                # Pydantic schemas (empty)
│   ├── services/               # Business logic (empty)
│   ├── ml/                     # ML/ASR pipeline (empty)
│   └── utils/                  # Utilities (empty)
│
├── alembic/
│   ├── env.py                  # Alembic environment
│   ├── script.py.mako          # Migration template
│   └── versions/               # Database migrations (empty)
│
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── pyproject.toml              # Python dependencies & tools config
├── alembic.ini                 # Alembic configuration
└── README.md                   # Backend documentation
```

**Key Technologies:**
- Python 3.12.12
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async)
- Alembic (migrations)
- Celery (background tasks)
- Pydantic v2 (validation)

---

## Frontend (Next.js)

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Home page
│   └── globals.css             # Global styles
│
├── components/                 # React components (empty)
│   └── ui/                     # shadcn/ui components (to be added)
│
├── lib/
│   └── utils.ts                # Utility functions
│
├── public/                     # Static assets (empty)
├── styles/                     # Additional styles (empty)
│
├── package.json                # Node dependencies
├── tsconfig.json               # TypeScript config
├── next.config.ts              # Next.js config
├── tailwind.config.ts          # Tailwind CSS config
├── postcss.config.mjs          # PostCSS config
├── .eslintrc.json              # ESLint config
├── .prettierrc                 # Prettier config
└── README.md                   # Frontend documentation
```

**Key Technologies:**
- Next.js 15 (App Router)
- React 19
- TypeScript
- Tailwind CSS + shadcn/ui
- TanStack Query
- Zustand (state)

---

## Configuration

```
config/
├── loki.yml                    # Loki logging config
├── prometheus.yml              # Prometheus metrics config
└── grafana/                    # Grafana dashboards (empty)
    ├── dashboards/
    └── datasources/
```

---

## Documentation

```
docs/
├── architecture/               # Architecture diagrams (empty)
├── api/                        # API documentation (empty)
├── security/                   # Security docs (empty)
├── adr/                        # Architecture Decision Records (empty)
├── licenses/                   # 3rd-party licenses (empty)
│
├── DEVELOPMENT_PHILOSOPHY.md   # Why we start minimal
├── PYTHON_UPGRADE.md           # Python 3.13→3.12 decision
└── STABILITY_REPORT.md         # System verification results
```

---

## Testing

```
e2e/
└── tests/                      # Playwright E2E tests (empty)

load-tests/
└── scenarios/                  # k6 load tests (empty)
```

---

## Scripts

```
scripts/
├── init-db.sql                 # Database initialization (empty)
├── redis.conf                  # Redis configuration (empty)
├── vault-init.sh               # Vault initialization (empty)
└── turnserver.conf             # coturn TURN/STUN config
```

---

## Git Ignored

The following are excluded from version control:

```
# Environment
.env

# Python
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
poetry.lock

# Node
node_modules/
.next/
.pnpm-store/

# IDE
.vscode/
.idea/
.DS_Store

# Secrets
*.pem
*.key
secrets/
vault-keys/
```

---

## Docker Compose Files

### `docker-compose.minimal.yml` (Default)
**Use:** `make up`
**Services:** PostgreSQL + Redis (2 containers)
**Purpose:** Daily development

### `docker-compose.yml` (Full Stack)
**Use:** `make up-full`
**Services:** All 11 services including observability
**Purpose:** Production-like testing

---

## Key Commands

```bash
# Development
make up                  # Start minimal services
make dev-backend         # Run FastAPI server
make dev-frontend        # Run Next.js dev server

# Database
make db-upgrade          # Run migrations
make db-revision MSG="desc"  # Create migration

# Quality
make lint                # Lint code
make format              # Format code
make test                # Run tests

# Utilities
make help                # Show all commands
```

---

## Package Statistics

| Component | Packages | Size |
|-----------|----------|------|
| Backend   | 218      | ~500MB |
| Frontend  | 723      | ~800MB |
| **Total** | **941**  | **~1.3GB** |

---

## Directory Status

| Directory | Status | Purpose |
|-----------|--------|---------|
| `backend/app/api/` | ✅ Ready | Build API endpoints here |
| `backend/app/models/` | ✅ Ready | Database models |
| `backend/alembic/versions/` | ✅ Ready | Migrations will go here |
| `frontend/components/` | ✅ Ready | React components |
| `docs/architecture/` | ✅ Ready | Add diagrams |
| `e2e/tests/` | ✅ Ready | E2E tests |
| `load-tests/scenarios/` | ✅ Ready | Load tests |

---

## Clean State

All temporary and unnecessary files removed:
- ✅ No `__pycache__` directories
- ✅ No `.DS_Store` files
- ✅ No redundant documentation
- ✅ No duplicate config files
- ✅ No build artifacts

---

## Next Steps

Ready to build:
1. Database schema (models + RLS)
2. Authentication (JWT)
3. API endpoints (CRUD)
4. Frontend pages
5. Tests

See `QUICKSTART.md` for development workflow.

---

**Status:** 🟢 Clean, organized, and ready for development
