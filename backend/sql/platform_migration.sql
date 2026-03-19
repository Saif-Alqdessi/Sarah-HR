-- =============================================================================
-- Sarah AI Platform — Database Migration & Storage Policies
-- =============================================================================
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- This creates all required tables and storage policies for the platform scaling.
--
-- PREREQUISITE: Before running this SQL, manually create the Storage bucket:
--   1. Go to Supabase Dashboard → Storage → New Bucket
--   2. Name: interview-audios
--   3. Public: Yes
--   4. File size limit: 100MB
--   5. Allowed MIME types: audio/webm, audio/wav, audio/mp3, audio/ogg
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. SCORING JOBS TABLE (queue for background scoring worker)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scoring_jobs (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    interview_id    UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id    UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message   TEXT,
    result_score_id UUID,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

-- Index for the worker's polling query: find oldest pending job
CREATE INDEX IF NOT EXISTS idx_scoring_jobs_status_created
    ON scoring_jobs (status, created_at ASC);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. SCORES TABLE (AI evaluation results from the scoring worker)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS scores (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    interview_id            UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id            UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,

    -- Overall scores
    final_score             REAL DEFAULT 0,
    ai_score                REAL DEFAULT 0,

    -- Per-category scores (0-100)
    communication_score     REAL DEFAULT 0,
    learning_score          REAL DEFAULT 0,
    stability_score         REAL DEFAULT 0,
    credibility_score       REAL DEFAULT 0,
    adaptability_score      REAL DEFAULT 0,
    field_knowledge_score   REAL DEFAULT 0,

    -- Detailed JSON data
    category_scores         JSONB DEFAULT '{}',
    strengths               JSONB DEFAULT '[]',
    weaknesses              JSONB DEFAULT '[]',
    improvement_areas       JSONB DEFAULT '[]',

    -- Salary recommendation
    salary_recommendation_min   REAL,
    salary_recommendation_max   REAL,
    salary_fit_score            REAL,
    salary_fit_rationale        TEXT,

    -- Cultural fit & risk
    cultural_fit_score      REAL,
    behavioral_flags        JSONB DEFAULT '[]',
    risk_indicators         JSONB DEFAULT '[]',

    -- Hiring recommendation
    hire_recommendation     TEXT,
    hire_confidence          REAL DEFAULT 0,
    next_steps_suggested    JSONB DEFAULT '[]',
    bottom_line_summary     TEXT,

    -- Metadata
    scoring_llm_model       TEXT DEFAULT 'groq/llama-3.3-70b',
    scoring_llm_temperature REAL DEFAULT 0.3,
    scored_at               TIMESTAMPTZ DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Index for looking up scores by interview
CREATE INDEX IF NOT EXISTS idx_scores_interview ON scores (interview_id);
CREATE INDEX IF NOT EXISTS idx_scores_candidate ON scores (candidate_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. ADD AUDIO COLUMNS TO INTERVIEWS TABLE (if they don't exist)
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    -- Audio storage path in Supabase Storage
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'audio_storage_path'
    ) THEN
        ALTER TABLE interviews ADD COLUMN audio_storage_path TEXT;
    END IF;

    -- Public URL for audio playback
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'audio_public_url'
    ) THEN
        ALTER TABLE interviews ADD COLUMN audio_public_url TEXT;
    END IF;

    -- Audio file size
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'audio_file_size_bytes'
    ) THEN
        ALTER TABLE interviews ADD COLUMN audio_file_size_bytes BIGINT;
    END IF;

    -- Audio duration estimate
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'audio_duration_seconds'
    ) THEN
        ALTER TABLE interviews ADD COLUMN audio_duration_seconds INTEGER;
    END IF;

    -- When recording stopped
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'recording_stopped_at'
    ) THEN
        ALTER TABLE interviews ADD COLUMN recording_stopped_at TIMESTAMPTZ;
    END IF;

    -- Is completed flag
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'is_completed'
    ) THEN
        ALTER TABLE interviews ADD COLUMN is_completed BOOLEAN DEFAULT FALSE;
    END IF;

    -- Completed at timestamp
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'interviews' AND column_name = 'completed_at'
    ) THEN
        ALTER TABLE interviews ADD COLUMN completed_at TIMESTAMPTZ;
    END IF;
END $$;


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. ADMIN USERS TABLE (for dashboard access control)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS admin_users (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'hr_viewer'
                    CHECK (role IN ('super_admin', 'hr_manager', 'hr_viewer')),
    is_active       BOOLEAN DEFAULT TRUE,
    auth_user_id    UUID UNIQUE,        -- Links to Supabase Auth user
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for auth lookups
CREATE INDEX IF NOT EXISTS idx_admin_users_auth ON admin_users (auth_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users (email);


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. SUPABASE STORAGE RLS POLICIES (for interview-audios bucket)
-- ─────────────────────────────────────────────────────────────────────────────
-- NOTE: These policies apply to the 'interview-audios' bucket.
-- The bucket must exist BEFORE running these policies.

-- Policy: Allow anyone to upload audio files (candidates are unauthenticated
-- in the current flow, so we use a permissive INSERT policy).
-- The file path must be under the 'interviews/' folder.
CREATE POLICY IF NOT EXISTS "Allow audio upload"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'interview-audios'
        AND (storage.foldername(name))[1] = 'interviews'
    );

-- Policy: Allow anyone to read audio files from the public bucket.
-- Since the bucket is public, this enables the admin dashboard to play audio.
CREATE POLICY IF NOT EXISTS "Allow public audio read"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'interview-audios'
    );

-- Policy: Only admin users can delete audio files.
CREATE POLICY IF NOT EXISTS "Admin can delete audio"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'interview-audios'
        AND EXISTS (
            SELECT 1 FROM admin_users
            WHERE auth_user_id = auth.uid()
            AND is_active = TRUE
            AND role IN ('super_admin', 'hr_manager')
        )
    );


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. MATERIALIZED VIEW FOR ADMIN DASHBOARD (optional performance boost)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_admin_dashboard AS
SELECT
    c.id              AS candidate_id,
    c.full_name,
    c.phone_number,
    c.email,
    c.target_role,
    c.years_of_experience,
    c.expected_salary,
    c.created_at      AS candidate_created_at,

    i.id              AS interview_id,
    i.status          AS interview_status,
    i.created_at      AS interview_created_at,
    i.completed_at,
    i.duration_seconds,
    i.is_completed,
    i.audio_public_url,
    i.credibility_score AS live_credibility_score,

    s.id              AS score_id,
    s.final_score,
    s.ai_score,
    s.communication_score,
    s.hire_recommendation,
    s.hire_confidence,
    s.bottom_line_summary
FROM candidates c
LEFT JOIN LATERAL (
    SELECT * FROM interviews
    WHERE candidate_id = c.id
    ORDER BY created_at DESC
    LIMIT 1
) i ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM scores
    WHERE interview_id = i.id
    ORDER BY scored_at DESC
    LIMIT 1
) s ON TRUE
ORDER BY c.created_at DESC;

-- Index on the materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dashboard_candidate
    ON mv_admin_dashboard (candidate_id);

-- To refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_admin_dashboard;


-- ─────────────────────────────────────────────────────────────────────────────
-- DONE
-- ─────────────────────────────────────────────────────────────────────────────
-- After running this SQL:
-- 1. Verify tables exist in Table Editor
-- 2. Verify storage policies in Storage → Policies
-- 3. Insert your admin user:
--    INSERT INTO admin_users (email, full_name, role)
--    VALUES ('your-email@example.com', 'Your Name', 'super_admin');
