# Next Task: Database Schema & RLS

## Objective
Create the foundational database schema with multi-tenant RLS (Row-Level Security) policies.

## What We'll Build

### 1. Base Models
- `tenants` - Organizations using the system
- `users` - User accounts with roles
- `patients` - Patient records (with tenant_id)
- `encounters` - Clinical encounters
- `notes` - Clinical notes (SOAP)
- `note_versions` - Immutable version history (WORM)
- `audit_events` - Append-only audit log

### 2. RLS Policies
Every table will have:
- `tenant_id UUID NOT NULL`
- RLS policy: `tenant_id = current_setting('app.tenant_id')::UUID`
- API views: `api_patients`, `api_encounters`, etc.

### 3. Alembic Migration
Create initial migration with:
- Tables + indexes
- RLS policies
- API views
- Test data (dev only)

## Acceptance Criteria

- [ ] All tables created with proper columns
- [ ] Every table has `tenant_id` column
- [ ] RLS enabled on all tables
- [ ] RLS policies block cross-tenant access
- [ ] API views created for each table
- [ ] Migration up/down tested
- [ ] Sample test data works
- [ ] Tests verify RLS isolation

## Files to Create

```
backend/app/models/
├── __init__.py
├── base.py              # Base model with tenant_id
├── tenant.py            # Tenant model
├── user.py              # User model
├── patient.py           # Patient model
├── encounter.py         # Encounter model
├── note.py              # Note model
└── audit.py             # Audit event model

backend/alembic/versions/
└── 2025_10_14_1200-initial_schema.py  # Migration

backend/tests/unit/
├── test_models.py       # Model tests
└── test_rls.py          # RLS security tests
```

## Estimated Time
4-6 hours for:
- Models: 2h
- Migration: 1h
- RLS policies: 1h
- Tests: 2h

## Commands

```bash
# Create migration
make db-revision MSG="initial schema with RLS"

# Apply migration
make db-upgrade

# Test RLS
poetry run pytest tests/unit/test_rls.py -v
```

## Next After This

Once database schema is done:
→ Authentication (JWT, login/register endpoints)
→ Basic CRUD API endpoints
→ Frontend login page

## Questions to Decide

1. **User roles:** What roles do we need? (physician, admin, patient?)
2. **Patient fields:** What patient data fields are required?
3. **Encounter types:** In-person, telemedicine, phone?
4. **SOAP sections:** Standard or customizable templates?

---

**Ready to start?** Let me know and I'll create the database models!
