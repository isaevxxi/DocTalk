.PHONY: help install up down clean test lint format

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

## Help
help: ## Show this help message
	@echo "$(BLUE)DokTalk - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

## Installation & Setup
install: ## Install all dependencies (backend + frontend)
	@echo "$(BLUE)Installing dependencies...$(NC)"
	cd backend && poetry install
	cd frontend && pnpm install
	@echo "$(GREEN)Dependencies installed successfully!$(NC)"

install-ml: ## Install backend with ML/ASR dependencies
	@echo "$(BLUE)Installing backend with ML dependencies...$(NC)"
	cd backend && poetry install --extras ml
	@echo "$(GREEN)Backend with ML dependencies installed!$(NC)"

setup: install ## Full setup (install + copy env)
	@echo "$(BLUE)Setting up environment...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN).env file created from .env.example$(NC)"; \
		echo "$(RED)Please edit .env with your configuration!$(NC)"; \
	else \
		echo "$(GREEN).env file already exists$(NC)"; \
	fi

## Docker & Services
up: ## Start ultra-minimal services (postgres, redis only)
	@echo "$(BLUE)Starting ultra-minimal services (postgres + redis)...$(NC)"
	docker-compose -f docker-compose.minimal.yml up -d
	@echo "$(GREEN)Services started! (2 containers)$(NC)"

up-storage: ## Add MinIO for file storage
	@echo "$(BLUE)Starting services with storage (postgres, redis, minio)...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)Services started! (3 containers)$(NC)"

up-full: ## Start ALL services (includes WebRTC, monitoring, etc.)
	@echo "$(BLUE)Starting full infrastructure...$(NC)"
	@echo "$(RED)Warning: This will download ~500MB of images$(NC)"
	docker-compose up -d
	@echo "$(GREEN)All services started! (11 containers)$(NC)"

down: ## Stop all services
	@echo "$(BLUE)Stopping services...$(NC)"
	docker-compose -f docker-compose.minimal.yml down 2>/dev/null || true
	docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
	docker-compose down 2>/dev/null || true
	@echo "$(GREEN)Services stopped!$(NC)"

clean: down ## Clean up containers, volumes, and build artifacts
	@echo "$(BLUE)Cleaning up...$(NC)"
	docker-compose -f docker-compose.minimal.yml down -v 2>/dev/null || true
	docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || true
	docker-compose down -v 2>/dev/null || true
	rm -rf backend/.mypy_cache backend/.pytest_cache backend/.ruff_cache
	rm -rf frontend/.next frontend/node_modules/.cache
	@echo "$(GREEN)Cleanup complete!$(NC)"

logs: ## Show logs from all services
	docker-compose -f docker-compose.minimal.yml logs -f 2>/dev/null || docker-compose -f docker-compose.dev.yml logs -f 2>/dev/null || docker-compose logs -f

ps: ## Show running services
	@echo "$(BLUE)Running Services:$(NC)"
	@docker-compose -f docker-compose.minimal.yml ps 2>/dev/null || docker-compose -f docker-compose.dev.yml ps 2>/dev/null || docker-compose ps 2>/dev/null || echo "No services running"

## Database
db-upgrade: ## Run database migrations (upgrade to head)
	@echo "$(BLUE)Running database migrations...$(NC)"
	cd backend && poetry run alembic upgrade head
	@echo "$(GREEN)Migrations applied!$(NC)"

db-downgrade: ## Rollback last database migration
	@echo "$(BLUE)Rolling back last migration...$(NC)"
	cd backend && poetry run alembic downgrade -1
	@echo "$(GREEN)Migration rolled back!$(NC)"

db-revision: ## Create a new database migration (usage: make db-revision MSG="description")
	@if [ -z "$(MSG)" ]; then \
		echo "$(RED)Error: Please provide a message with MSG=\"description\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Creating new migration: $(MSG)$(NC)"
	cd backend && poetry run alembic revision --autogenerate -m "$(MSG)"

db-reset: ## Reset database (down + up + migrate)
	@echo "$(BLUE)Resetting database...$(NC)"
	docker-compose -f docker-compose.minimal.yml down postgres 2>/dev/null || docker-compose -f docker-compose.dev.yml down postgres
	docker-compose -f docker-compose.minimal.yml up -d postgres 2>/dev/null || docker-compose -f docker-compose.dev.yml up -d postgres
	sleep 5
	$(MAKE) db-upgrade
	@echo "$(GREEN)Database reset complete!$(NC)"

## Development
dev-backend: ## Run backend development server
	@echo "$(BLUE)Starting backend development server...$(NC)"
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run frontend development server
	@echo "$(BLUE)Starting frontend development server...$(NC)"
	cd frontend && pnpm dev

dev-celery: ## Run Celery worker
	@echo "$(BLUE)Starting Celery worker...$(NC)"
	cd backend && poetry run celery -A app.worker worker --loglevel=info

dev: ## Run backend + frontend + celery concurrently (requires tmux or multiple terminals)
	@echo "$(RED)Note: This requires multiple terminal sessions$(NC)"
	@echo "$(BLUE)Terminal 1: make dev-backend$(NC)"
	@echo "$(BLUE)Terminal 2: make dev-frontend$(NC)"
	@echo "$(BLUE)Terminal 3: make dev-celery$(NC)"

## Testing
test: ## Run all tests (backend + frontend)
	@echo "$(BLUE)Running all tests...$(NC)"
	$(MAKE) test-backend
	$(MAKE) test-frontend
	@echo "$(GREEN)All tests complete!$(NC)"

test-backend: ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	cd backend && poetry run pytest

test-backend-cov: ## Run backend tests with coverage
	@echo "$(BLUE)Running backend tests with coverage...$(NC)"
	cd backend && poetry run pytest --cov --cov-report=html --cov-report=term

test-backend-rls: ## Run RLS security tests only
	@echo "$(BLUE)Running RLS tests...$(NC)"
	cd backend && poetry run pytest -m rls

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	cd frontend && pnpm test

test-frontend-cov: ## Run frontend tests with coverage
	@echo "$(BLUE)Running frontend tests with coverage...$(NC)"
	cd frontend && pnpm test:coverage

test-e2e: ## Run E2E tests
	@echo "$(BLUE)Running E2E tests...$(NC)"
	cd e2e && pnpm playwright test

## Code Quality
lint: ## Lint all code
	@echo "$(BLUE)Linting code...$(NC)"
	cd backend && poetry run ruff check .
	cd frontend && pnpm lint
	@echo "$(GREEN)Linting complete!$(NC)"

lint-fix: ## Lint and auto-fix issues
	@echo "$(BLUE)Linting and fixing...$(NC)"
	cd backend && poetry run ruff check --fix .
	cd frontend && pnpm lint --fix
	@echo "$(GREEN)Fixes applied!$(NC)"

format: ## Format all code
	@echo "$(BLUE)Formatting code...$(NC)"
	cd backend && poetry run black .
	cd frontend && pnpm format
	@echo "$(GREEN)Formatting complete!$(NC)"

typecheck: ## Type check all code
	@echo "$(BLUE)Type checking...$(NC)"
	cd backend && poetry run mypy .
	cd frontend && pnpm typecheck
	@echo "$(GREEN)Type checking complete!$(NC)"

check: lint typecheck test ## Run all checks (lint + typecheck + test)
	@echo "$(GREEN)All checks passed!$(NC)"

## Security & Compliance
security-scan: ## Run security scans
	@echo "$(BLUE)Running security scans...$(NC)"
	cd backend && poetry run bandit -r app/
	cd frontend && pnpm audit
	@echo "$(GREEN)Security scan complete!$(NC)"

audit: ## Run dependency audits
	@echo "$(BLUE)Auditing dependencies...$(NC)"
	cd backend && poetry show --outdated
	cd frontend && pnpm outdated
	@echo "$(GREEN)Audit complete!$(NC)"

## Build & Deploy
build: ## Build production images
	@echo "$(BLUE)Building production images...$(NC)"
	docker-compose build
	@echo "$(GREEN)Build complete!$(NC)"

build-backend: ## Build backend only
	@echo "$(BLUE)Building backend...$(NC)"
	cd backend && poetry build
	@echo "$(GREEN)Backend built!$(NC)"

build-frontend: ## Build frontend only
	@echo "$(BLUE)Building frontend...$(NC)"
	cd frontend && pnpm build
	@echo "$(GREEN)Frontend built!$(NC)"

## Documentation
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	@echo "$(RED)Documentation generation not yet implemented$(NC)"

docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation...$(NC)"
	@echo "$(RED)Documentation server not yet implemented$(NC)"

## Utilities
shell-backend: ## Open Python shell in backend environment
	cd backend && poetry shell

shell-db: ## Open PostgreSQL shell
	@docker-compose -f docker-compose.minimal.yml exec postgres psql -U doktalk_user -d doktalk 2>/dev/null || docker-compose -f docker-compose.dev.yml exec postgres psql -U doktalk_user -d doktalk

shell-redis: ## Open Redis CLI
	@docker-compose -f docker-compose.minimal.yml exec redis redis-cli -a password 2>/dev/null || docker-compose -f docker-compose.dev.yml exec redis redis-cli -a password

backup-db: ## Backup database
	@echo "$(BLUE)Backing up database...$(NC)"
	@docker-compose -f docker-compose.minimal.yml exec postgres pg_dump -U doktalk_user doktalk > backup_$$(date +%Y%m%d_%H%M%S).sql 2>/dev/null || docker-compose -f docker-compose.dev.yml exec postgres pg_dump -U doktalk_user doktalk > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backed up!$(NC)"

restore-db: ## Restore database (usage: make restore-db FILE=backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: Please provide a backup file with FILE=backup.sql$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Restoring database from $(FILE)...$(NC)"
	@docker-compose -f docker-compose.minimal.yml exec -T postgres psql -U doktalk_user doktalk < $(FILE) 2>/dev/null || docker-compose -f docker-compose.dev.yml exec -T postgres psql -U doktalk_user doktalk < $(FILE)
	@echo "$(GREEN)Database restored!$(NC)"

version: ## Show versions of all components
	@echo "$(BLUE)Component Versions:$(NC)"
	@echo "Python: $$(cd backend && poetry run python --version)"
	@echo "Node: $$(node --version)"
	@echo "pnpm: $$(pnpm --version)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker-compose --version)"
