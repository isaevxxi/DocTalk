# DokTalk (v1) — Ambient Scribe + Clinical Assistant (RU)

## Summary
DokTalk listens to the encounter (WebRTC), produces a SOAP draft/summary, suggests ICD-10 codes and order blocks. The physician edits and approves, then the data goes to the EHR/IS (copy-to-EHR, adapters to follow). Local storage, immutable audits (WORM), compliance with 152-FZ/323-FZ/965n.

## In-scope vs. Out-of-scope
**v1 Goals:**
- Ambient notes (RU), dictation and commands
- SOAP draft + age-based templates
- ICD-10 suggestions (candidates, not a diagnosis), explainability
- Copy-to-EHR, PDF/JSON export, version/audit history

**Out of scope for v1:**
- Auto-diagnosis/treatment plan (physician always in the loop)
- Full-fledged CDS; deep EHR integration — that's v2

## Architecture (v1 monolith)
- **Frontend:** Next.js 15, shadcn/ui, Tailwind, SSR/ISR
- **Real-time:** WebSocket (chat), WebRTC (video), SFU: Jitsi Videobridge, TURN/STUN: coturn
- **Backend:** Python 3.12+, FastAPI + Pydantic v2, Celery
- **Data:** PostgreSQL 16 (RLS, pgvector), Redis 8.2.2+ (ACL), MinIO (SSE-KMS, Object Lock/WORM)
- **ML/ASR:** Silero VAD → pyannote (diarization) → Whisper (CT2/ONNX, INT8) + RU medical term post-editor
- **Security:** Vault (BYOK per tenant), TLS everywhere, OPA (selectively)
- **Observability:** OpenTelemetry → Tempo/Jaeger, Prometheus, Loki, Grafana

Diagrams: `docs/architecture/*.drawio`

## Quick Start (local dev)
### Prerequisites
- Docker + Docker Compose
- Python 3.12.x, Node 22.x, pnpm 9.x
- Make, poetry/uv

### Environment Variables
See `.env.example`. Secrets are issued by Vault (see below).

### Running Locally
```bash
# Clone the repository
git clone <repository-url>
cd DocTalk

# Copy environment template
cp .env.example .env

# Start infrastructure services
docker-compose up -d postgres redis minio vault

# Backend setup
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload

# Frontend setup (in new terminal)
cd frontend
pnpm install
pnpm dev

# Start Celery workers (in new terminal)
cd backend
poetry run celery -A app.worker worker --loglevel=info
```

## Secrets & Keys
* Vault: per-tenant keys (BYOK), rotation policy, MinIO SSE-KMS wrapping
* Never commit `.env`; only `.env.example`

## Multi-tenancy & RLS
* `tenant_id` everywhere (NOT NULL)
* RLS policies for all tables; API accesses via `api_*` views
* Migrations: see `alembic/versions/*.py`

## Data Model
* `patients`, `encounters`, `notes`, `note_versions`, `audit_events` (append-only, hash-chain)
* `media_assets` (MinIO), `jobs` (Celery), `integrations`

## Quality & Metrics
* `time_to_draft`, `%_accepted_without_edits`, `ICD10_precision_after_review`, WER/CER

## Tests
* pytest + httpx; e2e with Playwright; load with k6
* Required: unit, RLS impermeability, migrations up/down

### Running Tests
```bash
# Backend unit tests
cd backend
poetry run pytest

# Frontend tests
cd frontend
pnpm test

# E2E tests
cd e2e
pnpm playwright test

# Load tests
cd load-tests
k6 run scenarios/encounter_flow.js
```

## Build & CI/CD
* GitLab CI: linters, tests, images; Argo CD — deploy
* SemVer + Conventional Commits

## Compliance (RU)
* **152-FZ:** personal data localization, RLS/ABAC, WORM audit
* **323-FZ:** medical recordkeeping and identification
* **Order 965n:** telemedicine consultation rules (recordings/consents)

## Licenses / 3rd-party
* Check licensing terms for pyannote/models

## Roadmap
* v1: monolith + copy-to-EHR
* v2: bidirectional sync of problems/orders/coding
* v3: contextual answers over patient data

## Documentation
- [Architecture](docs/architecture/README.md)
- [API Documentation](docs/api/README.md)
- [Security & Compliance](docs/security/README.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## Support & Contact
For issues and feature requests, please use the issue tracker.
