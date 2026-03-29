-- =============================================================================
-- Settings Tables: registration_weights + ai_settings
-- =============================================================================
-- Run this in Supabase SQL Editor to create the settings management tables.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. REGISTRATION_WEIGHTS TABLE (scoring weights for registration form fields)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS registration_weights (
    id              SERIAL PRIMARY KEY,
    field_key       TEXT NOT NULL,
    label_ar        TEXT NOT NULL,
    label_en        TEXT,
    weight          REAL NOT NULL DEFAULT 0.0 CHECK (weight >= 0 AND weight <= 1),
    role_target     TEXT NOT NULL DEFAULT 'all' CHECK (role_target IN ('cashier', 'supervisor', 'all')),
    description_ar  TEXT,
    display_order   INTEGER DEFAULT 99,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (field_key, role_target)
);

CREATE INDEX IF NOT EXISTS idx_registration_weights_role ON registration_weights (role_target, is_active);

-- Seed data for registration weights (cashier role)
INSERT INTO registration_weights (field_key, label_ar, label_en, weight, role_target, description_ar, display_order)
VALUES
    ('experience', 'سنوات الخبرة', 'Years of Experience', 0.25, 'cashier', 'وزن سنوات الخبرة في الوظيفة', 1),
    ('proximity', 'قرب السكن', 'Proximity to Branch', 0.20, 'cashier', 'وزن قرب السكن من الفرع', 2),
    ('academic_status', 'المسار الدراسي', 'Academic Status', 0.15, 'cashier', 'وزن الحالة الأكاديمية', 3),
    ('field_experience', 'خبرة ميدانية', 'Field Experience', 0.15, 'cashier', 'وزن الخبرة في المجال', 4),
    ('availability', 'التوفر الفوري', 'Immediate Availability', 0.10, 'cashier', 'وزن القدرة على البدء فوراً', 5),
    ('commitments', 'الالتزامات', 'Commitments', 0.10, 'cashier', 'وزن الالتزامات (صلاة، تدخين)', 6),
    ('salary_fit', 'توافق الراتب', 'Salary Fit', 0.05, 'cashier', 'وزن توافق الراتب المتوقع', 7)
ON CONFLICT (field_key, role_target) DO NOTHING;

-- Seed data for registration weights (supervisor role)
INSERT INTO registration_weights (field_key, label_ar, label_en, weight, role_target, description_ar, display_order)
VALUES
    ('experience', 'سنوات الخبرة', 'Years of Experience', 0.30, 'supervisor', 'وزن سنوات الخبرة في الوظيفة', 1),
    ('field_experience', 'خبرة ميدانية', 'Field Experience', 0.25, 'supervisor', 'وزن الخبرة في المجال', 2),
    ('academic_status', 'المسار الدراسي', 'Academic Status', 0.20, 'supervisor', 'وزن الحالة الأكاديمية', 3),
    ('proximity', 'قرب السكن', 'Proximity to Branch', 0.10, 'supervisor', 'وزن قرب السكن من الفرع', 4),
    ('availability', 'التوفر الفوري', 'Immediate Availability', 0.08, 'supervisor', 'وزن القدرة على البدء فوراً', 5),
    ('commitments', 'الالتزامات', 'Commitments', 0.05, 'supervisor', 'وزن الالتزامات (صلاة، تدخين)', 6),
    ('salary_fit', 'توافق الراتب', 'Salary Fit', 0.02, 'supervisor', 'وزن توافق الراتب المتوقع', 7)
ON CONFLICT (field_key, role_target) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. AI_SETTINGS TABLE (configurable AI parameters)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ai_settings (
    setting_key     TEXT PRIMARY KEY,
    setting_value   TEXT NOT NULL,
    data_type       TEXT NOT NULL DEFAULT 'string' CHECK (data_type IN ('string', 'number', 'boolean', 'json')),
    label_ar        TEXT NOT NULL,
    label_en        TEXT,
    description     TEXT,
    min_value       REAL,
    max_value       REAL,
    display_order   INTEGER DEFAULT 99,
    is_editable     BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed AI settings (interview scoring weights)
INSERT INTO ai_settings (setting_key, setting_value, data_type, label_ar, label_en, description, min_value, max_value, display_order)
VALUES
    ('weight_communication', '0.20', 'number', 'وزن التواصل', 'Communication Weight', 'Weight for communication category in final score', 0.0, 1.0, 1),
    ('weight_credibility', '0.20', 'number', 'وزن المصداقية', 'Credibility Weight', 'Weight for credibility category in final score', 0.0, 1.0, 2),
    ('weight_learning', '0.15', 'number', 'وزن التعلم', 'Learning Weight', 'Weight for learning category in final score', 0.0, 1.0, 3),
    ('weight_stability', '0.15', 'number', 'وزن الاستقرار', 'Stability Weight', 'Weight for stability category in final score', 0.0, 1.0, 4),
    ('weight_adaptability', '0.15', 'number', 'وزن المرونة', 'Adaptability Weight', 'Weight for adaptability category in final score', 0.0, 1.0, 5),
    ('weight_field_knowledge', '0.15', 'number', 'وزن الخبرة الميدانية', 'Field Knowledge Weight', 'Weight for field knowledge category in final score', 0.0, 1.0, 6),
    ('max_retry_attempts', '2', 'number', 'عدد مرات إعادة المحاولة', 'Max Retry Attempts', 'How many times Sarah retries a question before skipping', 1, 5, 7),
    ('max_validation_attempts', '3', 'number', 'محاولات التحقق القصوى', 'Max Validation Attempts', 'Maximum validation attempts per answer', 1, 5, 8),
    ('voice_strictness', 'medium', 'string', 'صرامة الصوت', 'Voice Strictness', 'Validation strictness level (low/medium/high)', NULL, NULL, 9)
ON CONFLICT (setting_key) DO NOTHING;


-- ─────────────────────────────────────────────────────────────────────────────
-- DONE
-- ─────────────────────────────────────────────────────────────────────────────
-- After running this SQL:
-- 1. Verify tables exist in Supabase Table Editor
-- 2. Check seed data is populated
-- 3. Backend endpoints will be added to admin.py for CRUD operations
