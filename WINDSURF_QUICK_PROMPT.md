# 🚀 WINDSURF QUICK PROMPT: API Routes & Frontend (45 min)

Copy this entire prompt and paste into Windsurf Cascade.

---

## 🎯 OBJECTIVE

Implement Steps 4 & 5 of the Context-Aware Sarah AI system:
- **Step 4**: Add API routes to fetch/use registration form data
- **Step 5**: Add frontend UI to display registration context

**DO NOT TOUCH**: Any files related to Groq Whisper, STT, transcription, or audio capture.

---

## 📂 FILES TO MODIFY

### 1. `backend/app/api/routes/candidates.py` - ADD NEW ENDPOINT

Add this function at the end of the file:

```python
@router.get("/{candidate_id}/registration-context")
async def get_registration_context(candidate_id: str):
    """Fetch registration form context for intelligent agent"""
    try:
        supabase = get_supabase_client()
        
        # Try RPC function first
        try:
            result = supabase.rpc('get_registration_context', {
                'p_candidate_id': candidate_id
            }).execute()
            if result.data:
                logger.info(f"✅ Loaded registration context via RPC for {candidate_id}")
                return result.data
        except Exception as rpc_error:
            logger.warning(f"RPC not available, using fallback: {rpc_error}")
        
        # Fallback: direct query
        result = supabase.table("candidates").select(
            "full_name_ar, years_of_experience, expected_salary, "
            "has_field_experience, proximity_to_branch, academic_status, "
            "can_start_immediately, prayer_regularity, is_smoker, "
            "desired_job_title, has_relatives_at_company, age_range, "
            "nationality, grooming_objection, social_security_issues, "
            "registration_form_data"
        ).eq("id", candidate_id).execute()
        
        if not result.data:
            logger.warning(f"No registration context found for {candidate_id}")
            return {}
        
        logger.info(f"✅ Loaded registration context for {candidate_id}")
        return result.data[0]
        
    except Exception as e:
        logger.exception(f"Error fetching registration context: {e}")
        return {}
```

---

### 2. `backend/app/api/routes/agent.py` - CREATE OR UPDATE

If this file doesn't exist, create it. Otherwise, update the existing agent response endpoint:

```python
"""Agent routes: intelligent interview responses with context awareness."""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.intelligent_agent import IntelligentHRAgent
from app.db.supabase_client import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)
agent = IntelligentHRAgent()


@router.post("/agent-response")
async def handle_agent_request(request: Request):
    """Generate intelligent response with registration form context"""
    try:
        body = await request.json()
        
        candidate_id = body.get("candidate_id")
        candidate_name = body.get("candidate_name")
        target_role = body.get("target_role")
        conversation_history = body.get("conversation_history", [])
        
        # NEW: Fetch registration context
        registration_form = {}
        try:
            supabase = get_supabase_client()
            result = supabase.table("candidates").select(
                "full_name_ar, years_of_experience, expected_salary, "
                "has_field_experience, proximity_to_branch, academic_status, "
                "can_start_immediately, prayer_regularity, is_smoker"
            ).eq("id", candidate_id).execute()
            
            if result.data and len(result.data) > 0:
                registration_form = result.data[0]
                logger.info(f"✅ Loaded registration context for {candidate_id}")
        except Exception as e:
            logger.warning(f"⚠️ Could not load registration context: {e}")
        
        # Call agent WITH registration context
        response = agent.generate_response(
            candidate_name=candidate_name,
            target_role=target_role,
            conversation_history=conversation_history,
            candidate_id=candidate_id,
            registration_form=registration_form  # ← NEW PARAMETER
        )
        
        return JSONResponse({
            "assistant": {"say": response["response"]},
            "current_stage": response.get("current_stage", "opening"),
            "detected_inconsistencies": response.get("detected_inconsistencies", [])
        })
        
    except Exception as e:
        logger.exception(f"Error in agent response: {e}")
        return JSONResponse(
            status_code=500,
            content={"assistant": {"say": "عذراً، حدث خطأ. ممكن تعيد الجواب؟"}}
        )


@router.post("/end-interview")
async def handle_end_of_interview(request: Request):
    """Handle end of interview with credibility scoring"""
    try:
        from app.services.credibility_scorer import CredibilityScorer
        
        body = await request.json()
        candidate_id = body.get("candidate_id")
        interview_id = body.get("interview_id")
        conversation_history = body.get("conversation_history", [])
        detected_inconsistencies = body.get("detected_inconsistencies", [])
        
        supabase = get_supabase_client()
        
        # Fetch registration form
        result = supabase.table("candidates").select("*").eq("id", candidate_id).execute()
        reg_form = result.data[0] if result.data else {}
        
        # Score credibility
        scorer = CredibilityScorer()
        credibility_data = scorer.score_credibility(
            registration_form=reg_form,
            transcript=conversation_history,
            detected_inconsistencies=detected_inconsistencies
        )
        
        logger.info(f"✅ Credibility: {credibility_data.get('credibility_score')}/100")
        
        # Save to scores table
        supabase.table("scores").insert({
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "credibility_score": credibility_data.get("credibility_score"),
            "credibility_level": credibility_data.get("credibility_level"),
            "credibility_assessment": credibility_data,
            "bottom_line_summary": credibility_data.get("bottom_line_summary", "")
        }).execute()
        
        return JSONResponse({"status": "success", "credibility": credibility_data})
        
    except Exception as e:
        logger.exception(f"Error in end-of-interview: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
```

---

### 3. `backend/app/main.py` - REGISTER ROUTER

Add to imports:
```python
from app.api.routes import agent
```

Add to router registrations:
```python
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
```

---

### 4. `frontend/app/interview/[candidateId]/page.tsx` - ADD UI

**Add imports:**
```typescript
import { useEffect, useState } from 'react';
```

**Add state variables:**
```typescript
const [registrationForm, setRegistrationForm] = useState<any>(null);
const [loadingContext, setLoadingContext] = useState(true);
```

**Add useEffect to fetch data:**
```typescript
useEffect(() => {
  const fetchRegistrationContext = async () => {
    try {
      const response = await fetch(`/api/candidates/${params.candidateId}/registration-context`);
      if (response.ok) {
        const data = await response.json();
        setRegistrationForm(data);
        console.log('✅ Loaded registration context:', data);
      }
    } catch (error) {
      console.error('Error loading registration context:', error);
    } finally {
      setLoadingContext(false);
    }
  };

  fetchRegistrationContext();
}, [params.candidateId]);
```

**Add this component BEFORE the main component:**
```typescript
const RegistrationContextPanel = ({ registrationForm, loading }: { registrationForm: any; loading: boolean }) => {
  if (loading) {
    return (
      <div className="bg-gray-100 border border-gray-200 rounded-lg p-4 mb-6 animate-pulse">
        <div className="h-4 bg-gray-300 rounded w-1/4 mb-3"></div>
        <div className="grid grid-cols-2 gap-3">
          <div className="h-3 bg-gray-300 rounded"></div>
          <div className="h-3 bg-gray-300 rounded"></div>
        </div>
      </div>
    );
  }

  if (!registrationForm || Object.keys(registrationForm).length === 0) return null;
  
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
      <h3 className="text-sm font-semibold text-blue-800 mb-3 flex items-center gap-2">
        <span>📋</span>
        <span>بيانات الطلب الإلكتروني</span>
      </h3>
      
      <div className="grid grid-cols-2 gap-3 text-sm">
        {registrationForm.years_of_experience && (
          <div>
            <span className="text-gray-600">الخبرة:</span>{' '}
            <span className="font-medium">{registrationForm.years_of_experience}</span>
          </div>
        )}
        
        {registrationForm.expected_salary && (
          <div>
            <span className="text-gray-600">الراتب المتوقع:</span>{' '}
            <span className="font-medium">{registrationForm.expected_salary}</span>
          </div>
        )}
        
        {registrationForm.has_field_experience && (
          <div>
            <span className="text-gray-600">خبرة بالمجال:</span>{' '}
            <span className="font-medium">{registrationForm.has_field_experience}</span>
          </div>
        )}
        
        {registrationForm.proximity_to_branch && (
          <div className="col-span-2">
            <span className="text-gray-600">قرب السكن:</span>{' '}
            <span className="font-medium">{registrationForm.proximity_to_branch}</span>
          </div>
        )}
        
        {registrationForm.can_start_immediately && (
          <div>
            <span className="text-gray-600">البدء فوراً:</span>{' '}
            <span className="font-medium">{registrationForm.can_start_immediately}</span>
          </div>
        )}
        
        {registrationForm.academic_status && (
          <div>
            <span className="text-gray-600">الدراسة:</span>{' '}
            <span className="font-medium">{registrationForm.academic_status}</span>
          </div>
        )}
      </div>
      
      <div className="mt-3 pt-3 border-t border-blue-200 text-xs text-blue-700">
        💡 سارة تستخدم هذه البيانات كسياق أثناء المقابلة
      </div>
    </div>
  );
};
```

**Add to render (at the top of the return statement):**
```typescript
return (
  <div className="min-h-screen bg-gray-50 p-6">
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">
        مقابلة صوتية - {candidate?.full_name}
      </h1>
      
      {/* NEW: Registration Context Panel */}
      <RegistrationContextPanel 
        registrationForm={registrationForm}
        loading={loadingContext}
      />
      
      {/* Rest of existing UI */}
    </div>
  </div>
);
```

---

## ✅ TESTING CHECKLIST

After implementation, verify:

1. **Backend endpoint works:**
   ```bash
   curl http://localhost:8001/api/candidates/YOUR_ID/registration-context
   ```

2. **Agent uses context:**
   - Check logs for "✅ Loaded registration context"
   - Sarah's questions should say "شفت بطلبك انك..."

3. **Frontend displays panel:**
   - Blue panel appears at top of interview page
   - Shows candidate's registration data
   - No errors in console

4. **Credibility scoring works:**
   - Complete interview
   - Check database for credibility_score in scores table

---

## 🚨 CRITICAL: DO NOT MODIFY

- ✋ `groq_transcriber.py`
- ✋ `transcription.py`
- ✋ Audio capture code
- ✋ WebRTC implementation

---

## 🎯 SUCCESS CRITERIA

When done:
- ✅ `/api/candidates/{id}/registration-context` endpoint exists
- ✅ `/api/agent/agent-response` fetches and passes registration form
- ✅ Frontend shows blue registration panel
- ✅ Sarah references form data in questions
- ✅ Credibility scores save to database
- ✅ No errors in logs or console

---

**Execute these changes and Sarah will become context-aware! 🚀**
