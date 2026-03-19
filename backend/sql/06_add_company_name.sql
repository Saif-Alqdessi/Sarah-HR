-- =============================================================================
-- Final Tweaks: Add company_name to candidates table
-- =============================================================================

-- 1. Add the company_name column if it doesn't already exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'candidates' AND column_name = 'company_name'
    ) THEN
        ALTER TABLE candidates ADD COLUMN company_name TEXT;
    END IF;
END $$;

-- 2. Update all existing candidate records to use 'Qabalan' as the company name
UPDATE candidates 
SET company_name = 'Qabalan' 
WHERE company_name IS NULL;

-- Note: When fetching candidate aaaaaaaa-bbbb-cccc-dddd-111111111111,
-- the company_name will now correctly reflect 'Qabalan'.
