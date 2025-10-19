-- Test data seed script for Phase 3 E2E testing
-- Creates minimal data needed to test the recording upload pipeline

-- Disable RLS temporarily for seeding
SET app.tenant_id = '00000000-0000-0000-0000-000000000001';

-- Create test tenant
INSERT INTO tenants (id, name, slug, is_active, data_localization_country, retention_years, contact_email, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Test Clinic',
    'test-clinic',
    true,
    'RU',
    7,
    'admin@testclinic.ru',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Create test physician user
INSERT INTO users (id, tenant_id, email, password_hash, is_active, full_name, role, medical_license_number, specialty, created_at, updated_at)
VALUES (
    '10000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'test@doctalk.ru',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/L4g9AKHL9nNWYKWFe',  -- password: "test123"
    true,
    'Dr. Test Physician',
    'physician',
    'RU-МЗ-12345',
    'General Practice',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Create test patient
INSERT INTO patients (id, tenant_id, full_name, date_of_birth, sex, mrn, phone, email, is_active, created_at, updated_at)
VALUES (
    '20000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Ivan Testov',
    '1980-01-15',
    'male',
    'TEST-001',
    '+7-900-123-45-67',
    'ivan.testov@example.ru',
    true,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Create test encounter (in_progress status)
INSERT INTO encounters (id, tenant_id, patient_id, physician_id, encounter_type, status, scheduled_at, started_at, chief_complaint, consent_recorded, created_at, updated_at)
VALUES (
    '30000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    '20000000-0000-0000-0000-000000000001'::uuid,
    '10000000-0000-0000-0000-000000000001'::uuid,
    'in_person',
    'in_progress',
    NOW() - INTERVAL '30 minutes',
    NOW() - INTERVAL '15 minutes',
    'General checkup and consultation',
    true,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Display created test data
SELECT 'Test data created successfully!' as message;
SELECT 'Tenant ID: 00000000-0000-0000-0000-000000000001' as tenant;
SELECT 'User ID:   10000000-0000-0000-0000-000000000001' as user;
SELECT 'Patient ID: 20000000-0000-0000-0000-000000000001' as patient;
SELECT 'Encounter ID: 30000000-0000-0000-0000-000000000001' as encounter;
