# DokTalk Quick Start Guide

## Current Setup: Ultra-Minimal (2 Containers)

✓ Running: **PostgreSQL + Redis only**
✓ Memory: ~200MB
✓ Startup: ~5 seconds

---

## Commands to Run Now

### 1. Start Services
```bash
make up

# If this is a fresh container, fix PostgreSQL auth for host connections:
bash scripts/fix-postgres-auth.sh
```

### 2. Start Backend Development Server
**Terminal 1:**
```bash
make dev-backend
```
This starts the FastAPI server at `http://localhost:8000`

### 3. Start Frontend Development Server
**Terminal 2:**
```bash
make dev-frontend
```
This starts Next.js at `http://localhost:3000`

### 4. Check Everything Works
```bash
# Check running services
make ps

# View logs
make logs

# Test database connection
make shell-db
# Inside psql shell, type: \dt (then \q to quit)

# Test Redis connection
make shell-redis
# Inside redis, type: ping (should return PONG, then exit)
```

---

## What You Can Build Right Now

With just PostgreSQL + Redis, you can:

✅ **Database models** - Patients, encounters, notes, users
✅ **REST API** - CRUD endpoints with FastAPI
✅ **Authentication** - JWT tokens, sessions (Redis)
✅ **Frontend UI** - React components, forms
✅ **Caching** - Redis for session/query caching
✅ **Background jobs** - Celery tasks (Redis as broker)
✅ **Database migrations** - Alembic
✅ **Row-Level Security** - Multi-tenant data isolation
✅ **Unit & integration tests** - pytest, Playwright

---

## When to Add More Services

### Need file uploads? → Add MinIO
```bash
make down
make up-storage  # PostgreSQL + Redis + MinIO (3 containers)
```

### Need WebRTC/video calls? → Add Jitsi
```bash
make down
make up-full  # All 11 containers (~500MB download)
```

### Need monitoring/tracing? → Add observability stack
```bash
make up-full  # Includes Prometheus, Grafana, Jaeger, Loki
```

---

## Recommended Development Flow

### Week 1-2: Core API & Database
```bash
make up                    # 2 containers
make dev-backend           # Terminal 1
make dev-frontend          # Terminal 2

# Create database models
make db-revision MSG="create patients table"
make db-upgrade

# Write endpoints, tests
# Build UI components
```

### Week 3-4: File Processing
```bash
make down
make up-storage           # Add MinIO for audio files

# Implement audio upload
# Add S3-compatible storage integration
```

### Week 5+: Advanced Features
```bash
make up-full              # Everything for WebRTC, monitoring

# Implement video consultations
# Set up distributed tracing
# Configure alerts
```

---

## Service Tier Breakdown

| Command | Containers | Use Case | Download |
|---------|-----------|----------|----------|
| `make up` | 2 | **Daily development** (NOW) | ~30MB |
| `make up-storage` | 3 | File processing | ~50MB |
| `make up-full` | 11 | Production-like testing | ~500MB |

---

## Quick Reference: Make Commands

```bash
# Services
make up              # Start minimal (postgres + redis)
make up-storage      # Add MinIO
make up-full         # Everything
make down            # Stop all
make ps              # Check status
make logs            # View logs

# Development
make dev-backend     # Start API server
make dev-frontend    # Start Next.js
make dev-celery      # Start background worker

# Database
make db-revision MSG="description"  # Create migration
make db-upgrade                      # Apply migrations
make db-downgrade                    # Rollback
make db-reset                        # Fresh start

# Code Quality
make lint            # Lint code
make format          # Format code
make test            # Run tests
make check           # All quality checks

# Utilities
make shell-db        # Open PostgreSQL shell
make shell-redis     # Open Redis CLI
make backup-db       # Backup database
make help            # Show all commands
```

---

## Next Steps for Development

1. ✅ **Services running** (PostgreSQL + Redis)
2. 🔨 **Create database schema** (patients, encounters, notes)
3. 🔨 **Build authentication** (JWT, user management)
4. 🔨 **REST API endpoints** (CRUD operations)
5. 🔨 **Frontend pages** (login, dashboard, encounters)
6. 🔨 **Tests** (unit tests for models/endpoints)

---

## Pro Tips

- **Keep it simple:** Don't add services until you need them
- **Run tests often:** `make test` before every commit
- **Use migrations:** Never modify models without creating a migration
- **Check logs:** `make logs` when debugging
- **Hot reload enabled:** Backend & frontend auto-refresh on file changes

---

**You're ready to code!** Start with `make dev-backend` and `make dev-frontend` in separate terminals.
