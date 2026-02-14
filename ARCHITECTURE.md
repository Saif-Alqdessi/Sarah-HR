1. SYSTEM ARCHITECTURE
High-Level Architecture Diagram
┌─────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  Next.js 14 (App Router) + Tailwind CSS                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Candidate    │  │ Voice AI     │  │ HR Dashboard │         │
│  │ Intake Form  │  │ Interview UI │  │ & Analytics  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                          API GATEWAY                             │
├─────────────────────────────────────────────────────────────────┤
│  Next.js API Routes (Middleware, Auth, Rate Limiting)           │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Backend (Python)                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Interview    │  │ AI Scoring   │  │ Analytics    │         │
│  │ Orchestrator │  │ Engine       │  │ Service      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                      INTEGRATION LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Vapi AI      │  │ Claude API   │  │ Deepgram STT │         │
│  │ (Voice)      │  │ (Orchestrate │  │ (Backup)     │         │
│  │              │  │  + Score)    │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  Supabase (PostgreSQL + Real-time + Storage)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Candidates   │  │ Interviews   │  │ Transcripts  │         │
│  │ Profiles     │  │ & Scores     │  │ & Audio      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
Technology Stack Justification
Voice Platform: Vapi AI (Recommended)

Why: Built specifically for conversational AI with native Claude integration
Sub-300ms latency for Arabic/English
Built-in phone system support for future expansion
Dynamic context injection during calls
Automatic STT + sentiment analysis
Alternative: Retell AI (better for phone-first), LiveKit (more control, higher complexity)

Frontend: Next.js 14 (App Router)

Server Components for SEO and initial load
React Server Actions for form submission
Streaming UI for real-time interview status

Backend: FastAPI

Async by default for handling concurrent interviews
Native Pydantic validation for type safety
Easy WebSocket support for real-time updates

Database: Supabase

PostgreSQL with Row Level Security (RLS)
Real-time subscriptions for HR dashboard updates
Built-in authentication
Storage buckets for audio recordings


2. DETAILED FILE STRUCTURE
bakery-ai-recruiter/
│
├── frontend/                          # Next.js Application
│   ├── app/
│   │   ├── (candidate)/              # Candidate-facing routes
│   │   │   ├── apply/
│   │   │   │   ├── page.tsx          # Intake form
│   │   │   │   └── layout.tsx
│   │   │   ├── interview/
│   │   │   │   ├── [sessionId]/
│   │   │   │   │   └── page.tsx      # Voice AI interview UI
│   │   │   │   └── complete/
│   │   │   │       └── page.tsx      # Thank you page
│   │   │   └── layout.tsx
│   │   │
│   │   ├── (hr)/                     # HR Dashboard routes
│   │   │   ├── dashboard/
│   │   │   │   ├── page.tsx          # Main dashboard
│   │   │   │   ├── candidates/
│   │   │   │   │   └── [id]/
│   │   │   │   │       └── page.tsx  # Candidate detail
│   │   │   │   └── analytics/
│   │   │   │       └── page.tsx      # Analytics view
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── layout.tsx            # HR layout with auth
│   │   │
│   │   ├── api/                      # API Routes
│   │   │   ├── candidates/
│   │   │   │   ├── route.ts          # POST new candidate
│   │   │   │   └── [id]/
│   │   │   │       └── route.ts      # GET candidate details
│   │   │   ├── interview/
│   │   │   │   ├── start/
│   │   │   │   │   └── route.ts      # Initialize Vapi session
│   │   │   │   ├── webhook/
│   │   │   │   │   └── route.ts      # Vapi webhooks
│   │   │   │   └── analyze/
│   │   │   │       └── route.ts      # Post-interview analysis
│   │   │   └── export/
│   │   │       └── route.ts          # Excel export
│   │   │
│   │   ├── layout.tsx                # Root layout
│   │   └── globals.css               # Tailwind imports
│   │
│   ├── components/
│   │   ├── candidate/
│   │   │   ├── IntakeForm.tsx
│   │   │   ├── VoiceInterface.tsx
│   │   │   └── InterviewProgress.tsx
│   │   ├── hr/
│   │   │   ├── CandidateCard.tsx
│   │   │   ├── ScoreVisualization.tsx
│   │   │   ├── FilterBar.tsx
│   │   │   └── ExportButton.tsx
│   │   ├── ui/                       # Shadcn components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   └── ...
│   │   └── shared/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   │
│   ├── lib/
│   │   ├── supabase/
│   │   │   ├── client.ts             # Client-side Supabase
│   │   │   └── server.ts             # Server-side Supabase
│   │   ├── vapi/
│   │   │   ├── client.ts             # Vapi SDK wrapper
│   │   │   └── config.ts             # Vapi configuration
│   │   ├── utils.ts                  # Utility functions
│   │   └── constants.ts              # App constants
│   │
│   ├── types/
│   │   ├── candidate.ts
│   │   ├── interview.ts
│   │   └── index.ts
│   │
│   ├── hooks/
│   │   ├── useVoiceInterview.ts
│   │   ├── useCandidates.ts
│   │   └── useRealtime.ts
│   │
│   ├── public/
│   │   ├── logo.svg
│   │   └── audio/
│   │       └── welcome.mp3
│   │
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                           # FastAPI Application
│   ├── app/
│   │   ├── main.py                   # FastAPI entry point
│   │   ├── config.py                 # Configuration management
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── interview.py      # Interview orchestration
│   │   │   │   ├── scoring.py        # Scoring endpoints
│   │   │   │   └── analytics.py      # Analytics endpoints
│   │   │   └── dependencies.py       # Dependency injection
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── interview_orchestrator.py
│   │   │   ├── ai_scoring_engine.py
│   │   │   ├── sentiment_analyzer.py
│   │   │   └── question_generator.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── candidate.py          # Pydantic models
│   │   │   ├── interview.py
│   │   │   └── score.py
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── supabase_client.py
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       ├── candidate_repo.py
│   │   │       └── interview_repo.py
│   │   │
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   ├── claude_client.py
│   │   │   ├── vapi_client.py
│   │   │   └── deepgram_client.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       └── validators.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_scoring.py
│   │   └── test_orchestration.py
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── database/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_indexes.sql
│   │   └── 003_rls_policies.sql
│   └── seed/
│       └── sample_data.sql
│
├── docs/
│   ├── API.md                        # API documentation
│   ├── DEPLOYMENT.md                 # Deployment guide
│   └── PROMPTS.md                    # System prompts
│
├── .github/
│   └── workflows/
│       ├── frontend-ci.yml
│       └── backend-ci.yml
│
├── docker-compose.yml
├── .gitignore
└── README.md

3. COMPREHENSIVE TECHNICAL ROADMAP (4 PHASES)
PHASE 1: Foundation & Core Infrastructure (Week 1-2)
Objectives

Setup development environment
Implement database schema
Build candidate intake flow
Establish API foundation

Tasks
Database Setup
sql-- Execute in Supabase SQL Editor
-- See full schema in Section 4
Frontend Foundation

 Initialize Next.js 14 project with TypeScript
 Configure Tailwind CSS + Shadcn UI
 Setup Supabase client (client & server utilities)
 Implement mobile-first intake form with validation
 Create form submission API route
 Add loading states and error handling

Backend Foundation

 Initialize FastAPI project structure
 Setup environment configuration (Pydantic Settings)
 Create Supabase repository layer
 Implement candidate creation endpoint
 Add request validation middleware
 Setup CORS for Next.js origin

Deliverables

✅ Working intake form that saves to database
✅ API documentation (FastAPI automatic docs)
✅ Database with proper indexes and RLS policies


PHASE 2: Voice AI Integration & Interview Logic (Week 3-4)
Objectives

Integrate Vapi AI for voice interviews
Implement adaptive question routing
Build real-time interview UI

Tasks
Vapi AI Setup

 Create Vapi account and obtain API keys
 Design assistant configuration in Vapi dashboard
 Implement context injection system (pass form data)
 Setup webhook endpoint for interview events
 Configure voice (recommend: female, warm, professional)
 Test Arabic-English code-switching

Interview Orchestration Service (backend/app/services/interview_orchestrator.py)
pythonclass InterviewOrchestrator:
    async def generate_questions(self, role: str, context: dict) -> List[Question]
    async def inject_context_to_vapi(self, session_id: str, context: dict)
    async def handle_interview_completion(self, transcript: dict)
Frontend Voice Interface

 Create VoiceInterface.tsx component
 Integrate Vapi Web SDK
 Display real-time transcription
 Add visual feedback (waveform, speaking indicator)
 Implement session persistence (handle reconnects)
 Mobile audio permissions handling

Question Generator (Uses Claude API)

 Create prompt templates for each role (Baker, Cashier, Driver)
 Implement dynamic question selection based on responses
 Add fallback questions for edge cases

Deliverables

✅ End-to-end voice interview experience
✅ Real-time transcription display
✅ Role-specific adaptive questioning
✅ Audio recordings stored in Supabase Storage


PHASE 3: AI Scoring Engine & Post-Interview Analysis (Week 5-6)
Objectives

Build multi-dimensional scoring system
Implement sentiment analysis
Create candidate ranking algorithm

Tasks
AI Scoring Engine (backend/app/services/ai_scoring_engine.py)

 Design scoring rubric (see detailed rubric below)
 Implement Claude API integration for scoring
 Create skill-matching algorithm per role
 Build sentiment analysis pipeline
 Generate "Bottom Line" summaries (1 sentence)
 Calculate composite AI Score (0-100)

Scoring Dimensions

Communication Quality (25 points)

Clarity, coherence, language proficiency


Relevant Experience (25 points)

Past work alignment with target role


Situational Responses (30 points)

Problem-solving, customer service mindset


Cultural Fit (10 points)

Enthusiasm, work ethic indicators


Sentiment/Confidence (10 points)

Vocal tone analysis (via Vapi sentiment data)



Analysis Pipeline
python# Triggered via webhook after interview completion
1. Receive full transcript from Vapi
2. Extract key phrases and timestamps
3. Call Claude API for structured evaluation
4. Calculate individual dimension scores
5. Generate bottom-line summary
6. Store results in database
7. Trigger real-time update to HR dashboard
Testing

 Create test transcripts for all roles
 Validate scoring consistency (run same transcript 5x)
 Benchmark processing time (<30 seconds)

Deliverables

✅ Automated scoring system
✅ Structured evaluation reports
✅ Bottom-line summaries for quick review


PHASE 4: HR Dashboard & Production Readiness (Week 7-8)
Objectives

Build comprehensive HR dashboard
Implement filtering and search
Add Excel export functionality
Production deployment

Tasks
HR Dashboard Frontend

 Implement authentication (Supabase Auth)
 Create candidate list view with real-time updates
 Build filter system (role, score range, date)
 Design candidate detail modal
 Add score visualizations (radial charts for dimensions)
 Implement pagination (50 candidates per page)

Dashboard Features

 Ranking System: Sort by AI Score, Date, Role
 Quick Actions: Approve, Reject, Flag for Review
 Bulk Operations: Export selected candidates
 Search: Name, phone, email fuzzy search
 Transcript Viewer: Highlighted key moments

Excel Export (frontend/app/api/export/route.ts)
typescript// Using exceljs library
- Candidate Info Sheet
- Detailed Scores Sheet
- Transcript Summaries Sheet
- Includes: Name, Role, AI Score, Sentiment, Bottom Line, Interview Date
Production Preparation

 Setup Vercel deployment for Next.js
 Deploy FastAPI on Railway/Render/AWS Lambda
 Configure production Supabase instance
 Setup monitoring (Sentry for errors)
 Add rate limiting (protect API endpoints)
 Implement CDN for audio files
 Create backup strategy for database
 Load testing (simulate 100 concurrent interviews)

Security Checklist

 Environment variables properly secured
 Row Level Security (RLS) enabled in Supabase
 API endpoints protected with authentication
 Input sanitization on all forms
 HTTPS enforcement
 Webhook signature verification (Vapi)

Deliverables

✅ Fully functional HR dashboard
✅ Excel export feature
✅ Production deployment
✅ Monitoring and logging
✅ Documentation for HR staff


4. DATABASE SCHEMA
sql-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CANDIDATES TABLE
-- ============================================
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Basic Information
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    target_role VARCHAR(50) NOT NULL CHECK (target_role IN ('baker', 'cashier', 'delivery_driver')),
    
    -- Metadata
    application_source VARCHAR(50) DEFAULT 'web_form',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes for fast lookups
    CONSTRAINT unique_phone UNIQUE(phone_number)
);

CREATE INDEX idx_candidates_target_role ON candidates(target_role);
CREATE INDEX idx_candidates_created_at ON candidates(created_at DESC);
CREATE INDEX idx_candidates_phone ON candidates(phone_number);

-- ============================================
-- INTERVIEWS TABLE
-- ============================================
CREATE TABLE interviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    
    -- Interview Session
    vapi_session_id VARCHAR(255) UNIQUE,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    -- Audio & Transcription
    audio_url TEXT,
    full_transcript JSONB, -- Structured transcript with timestamps
    
    -- Questions Asked (dynamic based on role)
    questions_asked JSONB, -- Array of {question, answer, timestamp}
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_interviews_candidate_id ON interviews(candidate_id);
CREATE INDEX idx_interviews_status ON interviews(status);
CREATE INDEX idx_interviews_completed_at ON interviews(completed_at DESC);

-- ============================================
-- SCORES TABLE
-- ============================================
CREATE TABLE scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    
    -- AI-Generated Scores (0-100 scale)
    ai_score INTEGER NOT NULL CHECK (ai_score >= 0 AND ai_score <= 100),
    
    -- Dimensional Scores
    communication_score DECIMAL(5,2) CHECK (communication_score >= 0 AND communication_score <= 25),
    experience_score DECIMAL(5,2) CHECK (experience_score >= 0 AND experience_score <= 25),
    situational_score DECIMAL(5,2) CHECK (situational_score >= 0 AND situational_score <= 30),
    cultural_fit_score DECIMAL(5,2) CHECK (cultural_fit_score >= 0 AND cultural_fit_score <= 10),
    sentiment_score DECIMAL(5,2) CHECK (sentiment_score >= 0 AND sentiment_score <= 10),
    
    -- Sentiment Analysis
    overall_sentiment VARCHAR(20) CHECK (overall_sentiment IN ('positive', 'neutral', 'negative')),
    confidence_level VARCHAR(20) CHECK (confidence_level IN ('high', 'medium', 'low')),
    
    -- Skill Matching
    skill_match_percentage INTEGER CHECK (skill_match_percentage >= 0 AND skill_match_percentage <= 100),
    matched_skills TEXT[], -- Array of matched skills
    missing_skills TEXT[], -- Array of skills gap
    
    -- AI Summary
    bottom_line_summary TEXT NOT NULL, -- Max 200 characters
    detailed_evaluation JSONB, -- Structured feedback per dimension
    
    -- Red Flags
    red_flags TEXT[], -- Array of concerning patterns
    
    -- Metadata
    scoring_model VARCHAR(50) DEFAULT 'claude-sonnet-4.5',
    scored_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_interview_score UNIQUE(interview_id)
);

CREATE INDEX idx_scores_ai_score ON scores(ai_score DESC);
CREATE INDEX idx_scores_candidate_id ON scores(candidate_id);
CREATE INDEX idx_scores_sentiment ON scores(overall_sentiment);

-- ============================================
-- HR USERS TABLE (for authentication)
-- ============================================
CREATE TABLE hr_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'recruiter' CHECK (role IN ('recruiter', 'manager', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- AUDIT LOG TABLE (optional but recommended)
-- ============================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hr_user_id UUID REFERENCES hr_users(id),
    candidate_id UUID REFERENCES candidates(id),
    action VARCHAR(50) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE hr_users ENABLE ROW LEVEL SECURITY;

-- Policy: Candidates can read their own data
CREATE POLICY "Candidates can view own data"
ON candidates FOR SELECT
USING (auth.uid()::text = id::text);

-- Policy: HR users can view all candidates
CREATE POLICY "HR can view all candidates"
ON candidates FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM hr_users
        WHERE hr_users.id = auth.uid()
    )
);

-- Similar policies for interviews and scores tables
CREATE POLICY "HR can view all interviews"
ON interviews FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM hr_users
        WHERE hr_users.id = auth.uid()
    )
);

CREATE POLICY "HR can view all scores"
ON scores FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM hr_users
        WHERE hr_users.id = auth.uid()
    )
);

-- ============================================
-- VIEWS FOR DASHBOARD
-- ============================================

-- Comprehensive candidate view with latest interview
CREATE VIEW vw_candidates_dashboard AS
SELECT 
    c.id,
    c.full_name,
    c.phone_number,
    c.email,
    c.target_role,
    c.created_at AS applied_at,
    i.id AS interview_id,
    i.status AS interview_status,
    i.completed_at AS interview_completed_at,
    s.ai_score,
    s.overall_sentiment,
    s.confidence_level,
    s.skill_match_percentage,
    s.bottom_line_summary,
    s.red_flags
FROM candidates c
LEFT JOIN LATERAL (
    SELECT * FROM interviews
    WHERE candidate_id = c.id
    ORDER BY created_at DESC
    LIMIT 1
) i ON TRUE
LEFT JOIN scores s ON s.interview_id = i.id;

-- Analytics view: Aggregate stats by role
CREATE VIEW vw_role_analytics AS
SELECT 
    target_role,
    COUNT(*) AS total_applicants,
    COUNT(CASE WHEN i.status = 'completed' THEN 1 END) AS completed_interviews,
    ROUND(AVG(s.ai_score), 2) AS avg_ai_score,
    ROUND(AVG(s.skill_match_percentage), 2) AS avg_skill_match
FROM candidates c
LEFT JOIN interviews i ON i.candidate_id = c.id
LEFT JOIN scores s ON s.interview_id = i.id
GROUP BY target_role;

-- ============================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_candidates_updated_at BEFORE UPDATE ON candidates
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_interviews_updated_at BEFORE UPDATE ON interviews
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

5. SYSTEM PROMPT FOR VOICE AGENT
Vapi Assistant Configuration
Primary System Prompt (Inject via Vapi Dashboard)
markdown# ROLE AND CONTEXT
You are Sara, a professional recruitment assistant for "Golden Crust Bakery," a large bakery chain. You are conducting a brief initial interview to assess candidates for {{target_role}} positions. You are warm, welcoming, and efficient.

# CANDIDATE CONTEXT (Injected dynamically)
- Candidate Name: {{candidate_name}}
- Target Role: {{target_role}}
- Phone Number: {{phone_number}}
- Application Date: {{application_date}}

# LANGUAGE HANDLING
- The candidate may speak in Arabic, English, or mix both languages (code-switching)
- Mirror the candidate's language preference naturally
- If they start in Arabic, respond in Arabic; if they switch to English, switch seamlessly
- Never comment on their language choice or ask them to pick one language
- Common Arabic phrases you should understand:
  * "ماشي" / "تمام" = Okay/Fine
  * "يعني" = I mean / like
  * "والله" / "صراحة" = Honestly
  * "شوي" = a little / some
  * "كتير" = a lot / many

# INTERVIEW STRUCTURE

## Opening (ALWAYS start with this)
"Hi {{candidate_name}}! I'm Sara from Golden Crust Bakery. Thank you for applying for the {{target_role}} position. This will be a short 3-minute conversation to learn more about you. Are you ready to start?"

[Wait for confirmation]

## Question Flow (Adaptive based on role)

### IF target_role == "baker":
1. **Experience Check**: "Tell me about any experience you have working in a kitchen or bakery environment."
2. **Situational Question**: "Imagine you're in the middle of preparing dough for tomorrow's bread, and the oven breaks down. What would you do?"
3. **Availability**: "Our bakery shifts start at 4 AM. Would you be comfortable with early morning hours?"

### IF target_role == "cashier":
1. **Customer Service**: "Describe a time when you helped a difficult customer. How did you handle it?"
2. **Situational Question**: "A customer claims we gave them the wrong change and becomes upset. Walk me through how you'd handle this."
3. **Skills**: "Are you comfortable using a cash register and handling money? Do you have any experience with POS systems?"

### IF target_role == "delivery_driver":
1. **Driving Record**: "Tell me about your driving experience. Do you have a valid driver's license and a clean driving record?"
2. **Situational Question**: "You're running late on a delivery due to traffic, and the customer calls asking where their order is. What do you say?"
3. **Physical Requirements**: "This job requires lifting up to 30 pounds and being on your feet for long periods. Is that okay for you?"

## Adaptive Follow-ups
- If the candidate gives a short answer (less than 10 words), ask: "Can you tell me a bit more about that?"
- If they mention relevant experience, probe: "That's interesting! How long did you do that for?"
- If they seem nervous or hesitant: "Take your time, there's no rush."

## Closing (ALWAYS end with this)
"Thank you {{candidate_name}}! You'll hear back from our team within 48 hours. We appreciate your time today!"

[End call]

# BEHAVIORAL GUIDELINES

## DO:
- Keep answers brief and conversational (2-3 sentences max)
- Show genuine interest with phrases like "That's great!" or "I see"
- Use the candidate's name 2-3 times during the conversation
- Speak at a moderate pace (not too fast for non-native speakers)
- Provide subtle encouragement: "You're doing great"
- If they apologize for their English/Arabic, say: "No worries at all, you're doing perfectly fine!"

## DON'T:
- Ask about age, religion, marital status, or nationality (illegal discrimination)
- Make promises about hiring: Never say "You're hired" or "You definitely got the job"
- Rush the candidate: Give them 10-15 seconds to think before prompting
- Interrupt: Let them finish their thoughts completely
- Ask more than 3 core questions (keep it brief)
- Use technical jargon or complicated English vocabulary

# HANDLING EDGE CASES

## If candidate is unresponsive or silent:
After 15 seconds: "Are you still there? Can you hear me okay?"
After 30 seconds: "I'm not getting a response. I'll end this call, but please feel free to call back when you're ready."

## If candidate asks about salary/benefits:
"That's a great question! Our HR team discusses compensation and benefits during the in-person interview stage. I'm just here to learn about your background today."

## If candidate seems confused:
"No problem! Let me rephrase that..." [restate question in simpler terms]

## If technical issues occur:
"I'm having some trouble with the connection. Let me try that question again..."

# TONE CALIBRATION
- **Warmth**: 70% (friendly but professional)
- **Formality**: 40% (conversational, not stiff)
- **Enthusiasm**: 60% (positive but not over-the-top)
- **Patience**: 90% (very patient with pauses and thinking time)

# SUCCESS CRITERIA
A successful interview is one where:
1. All 3 core questions are answered
2. The candidate feels respected and heard
3. The call completes in 3-5 minutes
4. You gather enough information for AI scoring
Context Injection Code (FastAPI Backend)
python# backend/app/services/interview_orchestrator.py

async def start_vapi_interview(candidate_id: str, form_data: dict):
    """
    Initialize Vapi call with dynamic context injection
    """
    from app.integrations.vapi_client import VapiClient
    
    vapi = VapiClient()
    
    # Prepare context variables
    context = {
        "candidate_name": form_data["full_name"],
        "target_role": form_data["target_role"],
        "phone_number": form_data["phone_number"],
        "application_date": datetime.now().strftime("%B %d, %Y")
    }
    
    # Create Vapi call with context
    call = await vapi.create_call(
        assistant_id="your-vapi-assistant-id",
        customer={
            "number": form_data["phone_number"],
            "name": form_data["full_name"]
        },
        assistant_overrides={
            "variableValues": context,
            "firstMessage": f"Hi {context['candidate_name']}! I'm Sara from Golden Crust Bakery..."
        }
    )
    
    # Store session in database
    await db.create_interview_session(
        candidate_id=candidate_id,
        vapi_session_id=call["id"],
        context=context
    )
    
    return call

6. HR DASHBOARD SCHEMA & UI DESIGN
Dashboard Data Model
Candidate Card Component Schema
typescriptinterface CandidateCard {
  id: string;
  fullName: string;
  targetRole: 'baker' | 'cashier' | 'delivery_driver';
  appliedAt: Date;
  
  // Interview Status
  interviewStatus: 'pending' | 'in_progress' | 'completed' | 'failed';
  interviewCompletedAt?: Date;
  
  // Scores (only if interview completed)
  aiScore?: number; // 0-100
  overallSentiment?: 'positive' | 'neutral' | 'negative';
  confidenceLevel?: 'high' | 'medium' | 'low';
  skillMatchPercentage?: number; // 0-100
  
  // Key Summary
  bottomLineSummary?: string; // Max 200 chars
  redFlags?: string[]; // Array of concerns
  
  // Quick Actions
  canScheduleFollowUp: boolean;
  canReject: boolean;
}
Detailed Score View Schema
typescriptinterface DetailedScoreView {
  candidateInfo: {
    fullName: string;
    phoneNumber: string;
    email?: string;
    targetRole: string;
    appliedAt: Date;
  };
  
  interviewDetails: {
    duration: number; // seconds
    completedAt: Date;
    audioUrl: string;
    transcriptSummary: string;
  };
  
  scoreBreakdown: {
    aiScore: number; // Composite 0-100
    dimensions: {
      communication: { score: number; max: 25; feedback: string };
      experience: { score: number; max: 25; feedback: string };
      situational: { score: number; max: 30; feedback: string };
      culturalFit: { score: number; max: 10; feedback: string };
      sentiment: { score: number; max: 10; feedback: string };
    };
  };
  
  skillAnalysis: {
    matchPercentage: number;
    matchedSkills: string[];
    missingSkills: string[];
  };
  
  sentimentAnalysis: {
    overall: 'positive' | 'neutral' | 'negative';
    confidence: 'high' | 'medium' | 'low';
    keyMoments: Array<{
      timestamp: string;
      text: string;
      sentiment: string;
    }>;
  };
  
  aiInsights: {
    bottomLine: string;
    strengths: string[];
    concerns: string[];
    recommendedAction: 'strong_hire' | 'interview' | 'reject' | 'needs_review';
  };
}
```

### Dashboard UI Components

**Main Dashboard Layout**
```
┌─────────────────────────────────────────────────────────────┐
│  Golden Crust Bakery - Recruitment Dashboard       [Profile]│
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Total Apps  │ │ Interviewed │ │ Avg Score   │           │
│  │    247      │ │     189     │ │    73/100   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                               │
│  Filters: [All Roles ▾] [All Scores ▾] [Last 7 Days ▾]     │
│  Search: [🔍 Search by name, phone...]     [Export Excel]   │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                      CANDIDATE LIST                          │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Ahmed Hassan                         Score: 87/100 🟢 │  │
│  │ Baker • Applied 2 hours ago                           │  │
│  │ ⭐ Strong hire - Excellent communication, 5 yrs exp   │  │
│  │ ✅ High confidence • 92% skill match                  │  │
│  │ [View Details] [Schedule Interview] [Reject]          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Layla Mohammed                       Score: 62/100 🟡 │  │
│  │ Cashier • Applied yesterday                           │  │
│  │ ⚠️  Needs review - Limited experience, medium fit     │  │
│  │ ⚡ Medium confidence • 68% skill match                │  │
│  │ [View Details] [Schedule Interview] [Reject]          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Omar Ali                             Score: 45/100 🔴 │  │
│  │ Delivery Driver • Applied 3 days ago                  │  │
│  │ ⛔ Not recommended - Poor communication, no license   │  │
│  │ 🚩 Red flags: No driving license mentioned            │  │
│  │ [View Details] [Archive]                              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  [Load More] Showing 20 of 247                               │
└─────────────────────────────────────────────────────────────┘
```

**Detailed Candidate View (Modal)**
```
┌─────────────────────────────────────────────────────────────┐
│  Ahmed Hassan - Detailed Evaluation              [✕ Close]  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐  ┌──────────────────────────┐ │
│  │ CANDIDATE INFO          │  │ AI SCORE: 87/100         │ │
│  │                         │  │                          │ │
│  │ Phone: +962-7X-XXX-XXXX │  │      ┌───────┐          │ │
│  │ Role: Baker             │  │      │  87   │          │ │
│  │ Applied: 2h ago         │  │      │ /100  │  🟢      │ │
│  │ Interview: 4m 23s       │  │      └───────┘          │ │
│  │                         │  │                          │ │
│  │ [▶️ Play Recording]     │  │ Strong Hire              │ │
│  └─────────────────────────┘  └──────────────────────────┘ │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  SCORE BREAKDOWN                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Communication (22/25)  ████████████████████░░      │    │
│  │ Experience (21/25)     ████████████████████░░      │    │
│  │ Situational (26/30)    ████████████████████░       │    │
│  │ Cultural Fit (9/10)    ████████████████████        │    │
│  │ Sentiment (9/10)       ████████████████████        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  AI BOTTOM LINE                                             │
│  ⭐ Ahmed is an excellent candidate with 5 years of        │
│  professional baking experience. He demonstrated strong    │
│  problem-solving skills and is comfortable with early      │
│  morning shifts. High confidence and enthusiasm.           │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  SKILL MATCH: 92%                                          │
│  ✅ Matched: Bread Making, Dough Preparation, Time Mgmt   │
│  ⚠️  Gap: Industrial Oven Experience (can be trained)     │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  TRANSCRIPT HIGHLIGHTS                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ 0:43 - "I worked at Al-Salam Bakery for 5 years..." │    │
│  │ 2:15 - [Situational Q] "I would check if we have    │    │
│  │        backup ovens and call maintenance..."         │    │
│  │ 3:50 - "Early mornings are fine, I'm a morning      │    │
│  │        person actually!"                             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  [📥 Download Full Transcript] [📧 Email to Hiring Manager]│
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  ACTIONS                                                    │
│  [✅ Schedule In-Person Interview] [❌ Reject] [📌 Flag]   │
└─────────────────────────────────────────────────────────────┘
Excel Export Format
Sheet 1: Candidate Overview
Full NamePhoneRoleApplied DateInterview StatusAI ScoreSentimentSkill MatchBottom LineAhmed Hassan+962...Baker2026-02-01Completed87Positive92%Excellent candidate with 5 years...
Sheet 2: Detailed Scores
CandidateCommunicationExperienceSituationalCultural FitSentimentTotalAhmed Hassan22/2521/2526/309/109/1087/100
Sheet 3: Red Flags & Notes
CandidateRed FlagsHR NotesOmar AliNo valid driving licenseNeeds follow-up

7. KEY TECHNICAL IMPLEMENTATION NOTES
Vapi Context Injection Best Practices
javascript// When starting interview from Next.js
const startInterview = async (candidateData) => {
  const response = await fetch('/api/interview/start', {
    method: 'POST',
    body: JSON.stringify({
      candidateId: candidateData.id,
      vapiConfig: {
        assistantId: process.env.VAPI_ASSISTANT_ID,
        variables: {
          candidate_name: candidateData.full_name,
          target_role: candidateData.target_role,
          phone_number: candidateData.phone_number
        }
      }
    })
  });
  
  const { vapiSessionId } = await response.json();
  
  // Initialize Vapi Web SDK
  const vapi = new Vapi(process.env.NEXT_PUBLIC_VAPI_KEY);
  await vapi.start(vapiSessionId);
};
Real-time Dashboard Updates (Supabase)
typescript// Listen for new scores in HR dashboard
const supabase = createClient();

useEffect(() => {
  const channel = supabase
    .channel('scores-updates')
    .on('postgres_changes', 
      { 
        event: 'INSERT', 
        schema: 'public', 
        table: 'scores' 
      }, 
      (payload) => {
        // Update UI with new candidate score
        updateCandidateList(payload.new);
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}, []);
Scoring Prompt for Claude
python# backend/app/services/ai_scoring_engine.py

SCORING_PROMPT = """
You are an expert HR evaluator for a bakery chain. Analyze this interview transcript and provide structured scoring.

TRANSCRIPT:
{transcript}

ROLE: {target_role}

Evaluate on these dimensions:
1. Communication Quality (0-25): Clarity, coherence, language proficiency
2. Relevant Experience (0-25): Past work alignment with role
3. Situational Responses (0-30): Problem-solving, practical thinking
4. Cultural Fit (0-10): Enthusiasm, work ethic indicators
5. Sentiment (0-10): Confidence, positivity in responses

Return ONLY valid JSON:
{{
  "scores": {{
    "communication": 22,
    "experience": 21,
    "situational": 26,
    "cultural_fit": 9,
    "sentiment": 9,
    "total": 87
  }},
  "sentiment_analysis": {{
    "overall": "positive",
    "confidence": "high"
  }},
  "skills": {{
    "matched": ["bread making", "time management"],
    "missing": ["industrial oven experience"]
  }},
  "bottom_line": "Excellent candidate with 5 years of professional baking experience and strong problem-solving skills.",
  "red_flags": [],
  "recommendation": "strong_hire"
}}
"""

8. DEPLOYMENT & SCALING CONSIDERATIONS
Infrastructure

Frontend: Vercel (automatic scaling, CDN)
Backend: Railway or AWS Lambda (auto-scale based on interview volume)
Database: Supabase Pro (connection pooling for high traffic)
Voice: Vapi handles scaling automatically

Performance Targets

Form submission: <500ms response time
Interview initiation: <2 seconds to connect
Voice latency: <300ms (handled by Vapi)
Scoring pipeline: <30 seconds post-interview
Dashboard load: <1 second initial render

Cost Estimates (1000 interviews/month)

Vapi: ~$200-300 (depends on minutes)
Claude API: ~$50-100 (scoring)
Supabase: $25 (Pro plan)
Vercel: Free (hobby) or $20 (Pro)
Total: ~$300-450/month

Monitoring

Sentry for error tracking
Vercel Analytics for frontend performance
Custom logging for interview completion rates
Alert on: Failed interviews >5%, Scoring errors, API rate limits