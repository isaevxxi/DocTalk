#!/bin/bash
# Seed development data via SQL
# This avoids the asyncpg connection issue by running SQL directly in the container

set -e

echo "🌱 Seeding development data..."

# Generate password hashes (using Python/bcrypt)
ADMIN_HASH=$(python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('admin123'))")
DOCTOR_HASH=$(python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('doctor123'))")

# Fixed UUIDs for dev
TENANT_ID="00000000-0000-0000-0000-000000000001"
ADMIN_ID="00000000-0000-0000-0000-000000000011"
PHYSICIAN_ID="00000000-0000-0000-0000-000000000012"
PATIENT1_ID="00000000-0000-0000-0000-000000000021"
PATIENT2_ID="00000000-0000-0000-0000-000000000022"

cat << EOF | docker exec -i doktalk-postgres psql -U doktalk_user -d doktalk
-- Set tenant context for RLS
SET LOCAL app.tenant_id = '${TENANT_ID}';

-- 1. Create tenant
INSERT INTO tenants (id, name, slug, is_active, data_localization_country, retention_years, contact_email, contact_phone)
VALUES (
    '${TENANT_ID}',
    'Central Clinic',
    'central-clinic',
    true,
    'RU',
    7,
    'admin@central-clinic.ru',
    '+7-495-123-4567'
);

-- 2. Create users
INSERT INTO users (id, tenant_id, email, password_hash, full_name, role, is_active, created_by)
VALUES (
    '${ADMIN_ID}',
    '${TENANT_ID}',
    'admin@central-clinic.ru',
    '${ADMIN_HASH}',
    'Администратор Системы',
    'admin',
    true,
    '${ADMIN_ID}'
);

INSERT INTO users (id, tenant_id, email, password_hash, full_name, role, phone, medical_license_number, specialty, is_active, created_by)
VALUES (
    '${PHYSICIAN_ID}',
    '${TENANT_ID}',
    'ivanov@central-clinic.ru',
    '${DOCTOR_HASH}',
    'Иванов Иван Иванович',
    'physician',
    '+7-916-123-4567',
    '78-12-345678',
    'Терапевт',
    true,
    '${ADMIN_ID}'
);

-- 3. Create patients
INSERT INTO patients (id, tenant_id, full_name, date_of_birth, sex, mrn, phone, email, address, is_active, notes, created_by)
VALUES (
    '${PATIENT1_ID}',
    '${TENANT_ID}',
    'Петров Петр Петрович',
    '1985-03-15',
    'male',
    'MRN-001',
    '+7-916-234-5678',
    'petrov@example.com',
    'Москва, ул. Ленина, д. 1, кв. 5',
    true,
    'Аллергия на пенициллин',
    '${ADMIN_ID}'
);

INSERT INTO patients (id, tenant_id, full_name, date_of_birth, sex, mrn, phone, email, address, is_active, created_by)
VALUES (
    '${PATIENT2_ID}',
    '${TENANT_ID}',
    'Сидорова Мария Александровна',
    '1992-07-22',
    'female',
    'MRN-002',
    '+7-916-345-6789',
    'sidorova@example.com',
    'Москва, ул. Пушкина, д. 10, кв. 15',
    true,
    '${ADMIN_ID}'
);

-- 4. Create encounters
INSERT INTO encounters (id, tenant_id, patient_id, physician_id, encounter_type, status, scheduled_at, started_at, completed_at, chief_complaint, diagnosis, consent_recorded, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000031',
    '${TENANT_ID}',
    '${PATIENT1_ID}',
    '${PHYSICIAN_ID}',
    'in_person',
    'completed',
    NOW() - INTERVAL '1 day 2 hours',
    NOW() - INTERVAL '1 day',
    NOW() - INTERVAL '1 day' + INTERVAL '30 minutes',
    'Кашель и повышенная температура',
    'ОРВИ (J06.9)',
    true,
    '${PHYSICIAN_ID}'
);

INSERT INTO encounters (id, tenant_id, patient_id, physician_id, encounter_type, status, scheduled_at, chief_complaint, consent_recorded, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000032',
    '${TENANT_ID}',
    '${PATIENT2_ID}',
    '${PHYSICIAN_ID}',
    'telemed',
    'scheduled',
    NOW() + INTERVAL '2 days',
    'Консультация по результатам анализов',
    true,
    '${ADMIN_ID}'
);

-- 5. Create note
INSERT INTO notes (id, tenant_id, encounter_id, content, status, current_version, finalized_at, finalized_by, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000041',
    '${TENANT_ID}',
    '00000000-0000-0000-0000-000000000031',
    'S (Subjective):
Пациент жалуется на кашель, повышенную температуру до 38.5°C, общую слабость.
Симптомы начались 3 дня назад.

O (Objective):
Температура: 38.2°C
Пульс: 88 уд/мин
АД: 120/80
ЧДД: 18/мин
При аускультации: жесткое дыхание, хрипов нет
Горло: гиперемия слизистой

A (Assessment):
Острая респираторная вирусная инфекция (ОРВИ), J06.9
Без осложнений

P (Plan):
1. Обильное питье
2. Парацетамол 500мг при температуре >38°C
3. Постельный режим 3-5 дней
4. Повторный осмотр при ухудшении состояния
5. Больничный лист на 5 дней',
    'final',
    1,
    NOW() - INTERVAL '1 day' + INTERVAL '35 minutes',
    '${PHYSICIAN_ID}',
    '${PHYSICIAN_ID}'
);

-- 6. Create note version (WORM table - INSERT only)
INSERT INTO note_versions (id, tenant_id, note_id, version, content, status, change_summary, created_by)
VALUES (
    '00000000-0000-0000-0000-000000000051',
    '${TENANT_ID}',
    '00000000-0000-0000-0000-000000000041',
    1,
    'S (Subjective):
Пациент жалуется на кашель, повышенную температуру до 38.5°C, общую слабость.
Симптомы начались 3 дня назад.

O (Objective):
Температура: 38.2°C
Пульс: 88 уд/мин
АД: 120/80
ЧДД: 18/мин
При аускультации: жесткое дыхание, хрипов нет
Горло: гиперемия слизистой

A (Assessment):
Острая респираторная вирусная инфекция (ОРВИ), J06.9
Без осложнений

P (Plan):
1. Обильное питье
2. Парацетамол 500мг при температуре >38°C
3. Постельный режим 3-5 дней
4. Повторный осмотр при ухудшении состояния
5. Больничный лист на 5 дней',
    'final',
    'Initial version',
    '${PHYSICIAN_ID}'
);

-- 7. Create audit events (hash chain will be computed by trigger)
INSERT INTO audit_events (id, tenant_id, event_type, user_id, resource_type, resource_id, event_data, ip_address, user_agent)
VALUES (
    '00000000-0000-0000-0000-000000000061',
    '${TENANT_ID}',
    'patient.created',
    '${ADMIN_ID}',
    'patient',
    '${PATIENT1_ID}',
    '{"action": "create", "mrn": "MRN-001"}',
    '127.0.0.1',
    'DokTalk/1.0'
);

INSERT INTO audit_events (id, tenant_id, event_type, user_id, resource_type, resource_id, event_data, ip_address, user_agent)
VALUES (
    '00000000-0000-0000-0000-000000000062',
    '${TENANT_ID}',
    'encounter.completed',
    '${PHYSICIAN_ID}',
    'encounter',
    '00000000-0000-0000-0000-000000000031',
    '{"action": "complete", "diagnosis": "ОРВИ"}',
    '127.0.0.1',
    'DokTalk/1.0'
);

-- Verify counts
SELECT 'Tenants: ' || COUNT(*) FROM tenants;
SELECT 'Users: ' || COUNT(*) FROM users;
SELECT 'Patients: ' || COUNT(*) FROM patients;
SELECT 'Encounters: ' || COUNT(*) FROM encounters;
SELECT 'Notes: ' || COUNT(*) FROM notes;
SELECT 'Note Versions: ' || COUNT(*) FROM note_versions;
SELECT 'Audit Events: ' || COUNT(*) FROM audit_events;

-- Verify hash chain
SELECT id, event_type,
       CASE WHEN prev_hash IS NULL THEN 'NULL (first event)' ELSE encode(prev_hash, 'hex') END as prev_hash,
       encode(current_hash, 'hex') as current_hash
FROM audit_events
ORDER BY created_at;
EOF

echo "✅ Development data seeded successfully!"
echo ""
echo "📋 Created:"
echo "  - 1 tenant: Central Clinic"
echo "  - 2 users: admin@central-clinic.ru (admin123), ivanov@central-clinic.ru (doctor123)"
echo "  - 2 patients: Петров П.П., Сидорова М.А."
echo "  - 2 encounters: 1 completed, 1 scheduled"
echo "  - 1 clinical note with version history"
echo "  - 2 audit events with hash chain"
echo ""
echo "🔐 Tenant ID: ${TENANT_ID}"
echo "🔑 Use: SET LOCAL app.tenant_id = '${TENANT_ID}' for RLS isolation"
