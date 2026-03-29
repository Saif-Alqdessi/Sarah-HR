-- ═══════════════════════════════════════════════════════════════════
-- Migration: Add review_status to interviews table
-- Run in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════

-- Step 1: Add review_status column with HR workflow states
-- These statuses represent where the candidate is in Qabalan's hiring pipeline
ALTER TABLE interviews
ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'new'
CHECK (review_status IN (
    'new',              -- Just completed, not yet reviewed by HR
    'viewed',           -- HR opened the profile
    'strong_candidate', -- Marked as promising by HR
    'weak_candidate',   -- Below threshold, unlikely hire
    'shortlisted',      -- Advanced to next round / in-person
    'hired',            -- Final decision: hired
    'rejected'          -- Final decision: rejected
));

-- Step 2: Add review metadata columns
ALTER TABLE interviews
ADD COLUMN IF NOT EXISTS reviewed_by TEXT,           -- Email of HR who reviewed
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,    -- When the review happened
ADD COLUMN IF NOT EXISTS hr_notes TEXT;               -- Free-text HR notes

-- Step 3: Index for fast filtering by review status
CREATE INDEX IF NOT EXISTS idx_interviews_review_status
    ON interviews (review_status);

-- Step 4: Update existing completed interviews to 'new' (if they have NULL)
UPDATE interviews
SET review_status = 'new'
WHERE review_status IS NULL AND (status = 'completed' OR is_completed = TRUE);
