-- =============================================================================
-- MIGRATION: Registration Fields for Qabalan Bakery
-- Adds all columns required by the registration form to the candidates table.
-- Safe to re-run: uses ADD COLUMN IF NOT EXISTS.
--
-- Run this in Supabase SQL Editor.
-- =============================================================================

-- ─────────────────────────────────────────────
-- Section 1: Personal Information
-- ─────────────────────────────────────────────

-- Date of birth (for age calculation)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS date_of_birth DATE;

-- Gender: ذكر | انثى
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT 'ذكر';

-- Nationality: أردني | جنسية أخرى
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS nationality TEXT DEFAULT 'أردني';

-- Marital status: اعزب | متزوج | مطلق | ارمل
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS marital_status TEXT;

-- Full residential address
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS detailed_residence TEXT;

-- ─────────────────────────────────────────────
-- Section 2: Job Information
-- ─────────────────────────────────────────────

-- Years of experience (integer, 0-50)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS years_of_experience INTEGER DEFAULT 0;

-- Field experience: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS has_field_experience TEXT DEFAULT 'لا';

-- Expected salary in JOD (integer, 200-2000)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS expected_salary INTEGER;

-- Preferred work shift: صباحي | مسائي | أي وردية
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS preferred_schedule TEXT;

-- Immediate availability: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS can_start_immediately TEXT;

-- ─────────────────────────────────────────────
-- Section 3: Additional Info
-- ─────────────────────────────────────────────

-- Age group: 18-21 | 22-25 | 26 فأكثر
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS age_range TEXT;

-- Academic path: لا يوجد نية لاستكمال الدراسة | أكمل مسيرتي الدراسية | انتهيت من المسيرة الدراسية (متخرج)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS academic_status TEXT;

-- Academic qualification: مؤهل للجامعة (توجيهي ناجح) | توجيهي راسب | جامعي | متخرج
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS academic_qualification TEXT;

-- Proximity to branch (EXACT strings from Analysis.csv):
-- قريب وأحضر مشياً على الاقدام | قريب بنفس المنطقة واحضر مواصلات | خارج المنطقة وأحضر مواصلات أو تكسي | خارج المحافظة
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS proximity_to_branch TEXT;

-- Has relatives at company: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS has_relatives_at_company TEXT;

-- Previously worked at Qabalan: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS previously_at_qabalan TEXT DEFAULT 'لا';

-- Social security issues: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS social_security_issues TEXT DEFAULT 'لا';

-- ─────────────────────────────────────────────
-- Section 4: Personal Commitments
-- ─────────────────────────────────────────────

-- Prayer regularity: نعم الحمد لله | ليس بشكل منتظم
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS prayer_regularity TEXT;

-- Smoker: نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS is_smoker TEXT;

-- Grooming objection (beard/hair): نعم | لا
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS grooming_objection TEXT;

-- ─────────────────────────────────────────────
-- Section 5: Metadata
-- ─────────────────────────────────────────────

-- Company name (always 'Qabalan' for this form)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS company_name TEXT DEFAULT 'Qabalan';

-- Registration source: web_form | manual | import
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS application_source TEXT DEFAULT 'web_form';

-- Raw JSON blob of entire form submission (backup)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS registration_form_data JSONB;

-- Email (optional)
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS email TEXT;

-- ─────────────────────────────────────────────
-- Indexes for common queries
-- ─────────────────────────────────────────────

-- Speed up phone-number uniqueness checks
CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_phone_unique
    ON candidates (phone_number);

-- Speed up admin dashboard filtering
CREATE INDEX IF NOT EXISTS idx_candidates_target_role
    ON candidates (target_role);

CREATE INDEX IF NOT EXISTS idx_candidates_nationality
    ON candidates (nationality);

CREATE INDEX IF NOT EXISTS idx_candidates_created_at
    ON candidates (created_at DESC);

-- ─────────────────────────────────────────────
-- Force-set company_name for ALL existing rows
-- ─────────────────────────────────────────────

UPDATE candidates
SET company_name = 'Qabalan'
WHERE company_name IS NULL OR company_name != 'Qabalan';

-- ─────────────────────────────────────────────
-- Done! Verify with:
--   SELECT column_name, data_type, column_default
--   FROM information_schema.columns
--   WHERE table_name = 'candidates'
--   ORDER BY ordinal_position;
-- ─────────────────────────────────────────────
