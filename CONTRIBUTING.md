# Contributing to DokTalk

## Workflow
- Issue → `TASK.md` → PR → Review → Merge
- Git: `main` (prod), `develop` (int), feature branches `feat/<scope>`

## Branch Naming Convention
- `feat/<scope>` - New features (e.g., `feat/soap-generation`)
- `fix/<scope>` - Bug fixes (e.g., `fix/rls-policy-patients`)
- `docs/<scope>` - Documentation updates
- `refactor/<scope>` - Code refactoring
- `test/<scope>` - Test additions or updates
- `chore/<scope>` - Build/tooling changes

## Commit Message Format
We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style/formatting (no logic change)
- `refactor`: Code restructuring
- `test`: Adding or updating tests
- `chore`: Tooling, dependencies, config

**Examples:**
```
feat(api): add ICD-10 suggestion endpoint

Implements the /api/v1/encounters/{id}/suggest-codes endpoint
with explainability metadata for each candidate code.

Closes #42
```

```
fix(rls): correct tenant_id filter in api_encounters view

The view was missing tenant_id filtering for joined tables,
allowing cross-tenant data leakage in edge cases.

Fixes #87
```

## Task Template (TASK.md)

Each significant task should have a `TASK.md` file in the issue or PR description:

```markdown
# Task Title

## Description
Briefly: what's needed and why; link to metrics/risks.

## Contracts & API
- Endpoints/events: methods, schemas (Pydantic v2), response codes
- UI: routes/components

## Data & Migrations
- Tables/indexes/views `api_*`
- RLS policies (example roles)
- Alembic up/down, seeds

## Security & Compliance
- PII? Yes/No. Where stored? Links to Vault/MinIO.
- Audit events (what we log)

## Observability
- Metrics (Prom), trace spans (OTel), logs

## Tests
- Unit (what/where), e2e (scenario), RLS (negative/positive)

## Acceptance Criteria (mandatory)
- [ ] List all AC as a checklist that can be run through

## Rollout/Backout
- Flags/migrations/data; how to roll back

## Documentation
- What to update in README/ADR/CHANGELOG
```

## Definition of Done (DoD)

Every PR must satisfy:

* [ ] Code covered by tests (new functionality ≥ 70% line; critical paths — 100%)
* [ ] Migrations up/down, RLS policies tested
* [ ] Linters/typing green (ruff/black/mypy; eslint/tsc)
* [ ] Metrics/logs/traces added
* [ ] README/ADR/CHANGELOG updated
* [ ] No PII in logs/metrics; secrets only via Vault
* [ ] PR description includes risks and rollback plan

## Code Review Checklist

Reviewers must verify:

* [ ] RLS and `tenant_id` in every new object
* [ ] No direct access to "raw" tables from API
* [ ] Query efficiency (indexes, N+1)
* [ ] PII data flow is clear and constrained
* [ ] No side effects in handlers (background via Celery)
* [ ] Input validation and proper error statuses
* [ ] Proper error handling and status codes
* [ ] Security implications documented
* [ ] Performance considerations addressed

## Development Setup

### Prerequisites
- Docker 24+ with Docker Compose
- Python 3.12.x
- Node 22.x
- pnpm 9.x
- Make
- poetry or uv

### Initial Setup
```bash
# 1. Clone and enter directory
git clone <repository-url>
cd DocTalk

# 2. Set up environment
cp .env.example .env
# Edit .env with your local values

# 3. Start infrastructure
docker-compose up -d

# 4. Backend setup
cd backend
poetry install
poetry run alembic upgrade head

# 5. Frontend setup
cd ../frontend
pnpm install

# 6. Verify setup
make test
```

## Testing Requirements

### Backend Tests
```bash
cd backend
poetry run pytest                    # All tests
poetry run pytest --cov             # With coverage
poetry run pytest -m security       # Security tests only
poetry run pytest -m rls            # RLS tests only
```

### Frontend Tests
```bash
cd frontend
pnpm test              # Unit tests
pnpm test:e2e         # E2E tests
pnpm test:coverage    # With coverage
```

### Test Coverage Requirements
- **Minimum:** 70% line coverage for new code
- **Critical paths:** 100% coverage (auth, RLS, PII handling, audit logging)
- **Security tests:** All RLS policies must have positive and negative tests

### RLS Test Examples
```python
# Positive test: user can access their tenant's data
def test_rls_allows_same_tenant_access(db, tenant_a_user):
    set_tenant_context(db, tenant_a_user.tenant_id)
    result = db.execute("SELECT * FROM api_patients")
    assert len(result) > 0

# Negative test: user cannot access other tenant's data
def test_rls_blocks_cross_tenant_access(db, tenant_a_user, tenant_b_patient):
    set_tenant_context(db, tenant_a_user.tenant_id)
    result = db.execute(
        "SELECT * FROM api_patients WHERE id = :id",
        {"id": tenant_b_patient.id}
    )
    assert len(result) == 0
```

## Code Quality

### Python
```bash
# Linting and formatting
poetry run ruff check .
poetry run black .
poetry run mypy .

# Or use make targets
make lint-py
make format-py
```

### TypeScript/JavaScript
```bash
# Linting and formatting
pnpm lint
pnpm format

# Type checking
pnpm typecheck
```

### Pre-commit Hooks
We recommend installing pre-commit hooks:
```bash
pre-commit install
```

## Security & Compliance Guidelines

### Row-Level Security (RLS)
- **ALWAYS** include `tenant_id` in new tables
- **NEVER** query base tables directly from API code
- **ALWAYS** use `api_*` views that enforce RLS
- **MUST** write both positive and negative RLS tests

### Personal Data (PII)
- **Identify** all PII fields in TASK.md
- **Encrypt** at rest (MinIO SSE-KMS) and in transit (TLS)
- **Never** log PII in plain text
- **Sanitize** PII in traces/metrics
- **Document** data flow and retention

### Secrets Management
- **Never** commit secrets to git
- **Always** use Vault for secrets
- **Rotate** keys per policy
- **Use** per-tenant BYOK where applicable

### Audit Logging
- **Log** all access to PII
- **Log** all clinical actions (read/write/approve)
- **Use** append-only `audit_events` table
- **Include** hash chain for immutability

## Migration Guidelines

### Creating Migrations
```bash
cd backend
poetry run alembic revision -m "description"
```

### Migration Checklist
* [ ] Both `upgrade()` and `downgrade()` implemented
* [ ] RLS policies for new tables
* [ ] Indexes for performance
* [ ] Data migrations are idempotent
* [ ] Tested on copy of production-like data
* [ ] Rollback plan documented

### RLS Policy Template
```sql
-- Create table with tenant_id
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    -- other fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Policy for tenant isolation
CREATE POLICY tenant_isolation ON patients
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- Create API view
CREATE VIEW api_patients AS
    SELECT * FROM patients
    WHERE tenant_id = current_setting('app.tenant_id')::UUID;
```

## Pull Request Process

1. **Create branch** from `develop`
2. **Implement** following TASK.md acceptance criteria
3. **Write tests** to meet DoD
4. **Run linters** and tests locally
5. **Update docs** (README, ADR, CHANGELOG if needed)
6. **Create PR** with template filled out
7. **Address review** comments
8. **Squash merge** after approval

### PR Template
```markdown
## Summary
Brief description of changes

## Related Issue
Closes #123

## Changes
- Added/Modified/Removed X
- Updated Y

## Security Implications
- PII handling: [describe]
- New permissions: [describe]
- RLS changes: [describe]

## Testing
- [ ] Unit tests added/updated
- [ ] E2E tests added/updated
- [ ] RLS tests (positive/negative)
- [ ] Manual testing completed

## Rollback Plan
How to revert these changes if needed

## Checklist
- [ ] DoD satisfied
- [ ] Migrations up/down tested
- [ ] Docs updated
- [ ] No PII in logs
```

## Architecture Decision Records (ADR)

For significant architectural changes, create an ADR:

```bash
docs/adr/NNNN-title-in-kebab-case.md
```

**Template:**
```markdown
# ADR-NNNN: Title

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Context
What is the issue we're addressing?

## Decision
What are we doing about it?

## Consequences
What becomes easier or harder?

## Alternatives Considered
What other options did we evaluate?
```

## Getting Help

- Check documentation in `docs/`
- Review existing ADRs
- Ask in team channels
- Tag relevant experts in issues/PRs

## License Compliance

- **Verify licenses** for all dependencies
- **Document** in `docs/licenses/`
- **Special attention** to ML model licenses (e.g., pyannote)
- **No GPL** in backend services (to avoid copyleft issues)

## Regulatory Compliance (RU)

All contributions must maintain compliance with:
- **152-FZ:** Personal data protection and localization
- **323-FZ:** Medical record keeping requirements
- **Order 965n:** Telemedicine consultation rules

When in doubt about compliance implications, flag for review.
