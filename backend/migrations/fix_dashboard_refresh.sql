-- ═══════════════════════════════════════════════════════════════════
-- Dashboard Fix Script
-- Run this in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════

-- STEP 1: Force refresh the materialized view with current data
REFRESH MATERIALIZED VIEW mv_admin_dashboard;

-- STEP 2: Verify interviews have correct status
-- Some interviews may have is_completed=true but status != 'completed'
UPDATE interviews
SET status = 'completed'
WHERE is_completed = TRUE
  AND status != 'completed';

-- STEP 3: Create a trigger that auto-refreshes the MV on interview completion
-- This ensures the dashboard is ALWAYS up-to-date
CREATE OR REPLACE FUNCTION trigger_refresh_dashboard()
RETURNS TRIGGER AS $$
BEGIN
    -- Only refresh when an interview is marked completed
    IF NEW.status = 'completed' OR NEW.is_completed = TRUE THEN
        PERFORM refresh_admin_dashboard();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS trg_refresh_dashboard ON interviews;

-- Create trigger
CREATE TRIGGER trg_refresh_dashboard
    AFTER UPDATE OF status, is_completed ON interviews
    FOR EACH ROW
    EXECUTE FUNCTION trigger_refresh_dashboard();

-- STEP 4: Also refresh MV when a new score is inserted
CREATE OR REPLACE FUNCTION trigger_refresh_dashboard_on_score()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM refresh_admin_dashboard();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_refresh_dashboard_on_score ON scores;

CREATE TRIGGER trg_refresh_dashboard_on_score
    AFTER INSERT ON scores
    FOR EACH ROW
    EXECUTE FUNCTION trigger_refresh_dashboard_on_score();

-- ═══════════════════════════════════════════════════════════════════
-- VERIFICATION: Check that data is now visible
-- ═══════════════════════════════════════════════════════════════════

-- Should show actual counts now
SELECT 'candidates' AS source, COUNT(*) AS total FROM candidates
UNION ALL
SELECT 'interviews', COUNT(*) FROM interviews
UNION ALL
SELECT 'completed_interviews', COUNT(*) FROM interviews WHERE status = 'completed' OR is_completed = TRUE
UNION ALL
SELECT 'scores', COUNT(*) FROM scores
UNION ALL
SELECT 'mv_dashboard_rows', COUNT(*) FROM mv_admin_dashboard;
