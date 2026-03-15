# 🚀 WINDSURF/CLAUDE SONNET MASTER PROMPT
# Arabic-First Backend Implementation for Sarah AI

**Model**: Claude Sonnet 4.6 (Thinking Mode Recommended)  
**Estimated Time**: 45-60 minutes  
**Complexity**: Medium-High (Database Integration + Dialect Enhancement)

---

## 📋 MISSION OVERVIEW

Transform the Sarah AI backend to work with an **Arabic-first database schema** where:
- All yes/no fields use 'نعم'/'لا' strings (NOT booleans)
- Roles are strictly bakery-related (NO software developers)
- Questions come from database `question_bank` table (NOT hardcoded)
- Interview responses use pure **Jordanian Arabic dialect** (Amman)

---

## 🗄️ DATABASE SCHEMA (Already Created by User)

The user has already executed the SQL reset script. The database now has:

### Table: `candidates`
```sql
-- All boolean fields are now VARCHAR with Arabic values
has_field_experience VARCHAR(5) CHECK IN ('نعم', 'لا')
is_smoker VARCHAR(5) CHECK IN ('نعم', 'لا')
previously_at_qabalan VARCHAR(5) CHECK IN ('نعم', 'لا')
gender VARCHAR(10) CHECK IN ('ذكر', 'انثى')
target_role VARCHAR(100) CHECK IN ('خباز', 'كاشير', 'عامل نظافة', ...)
```

### Table: `question_bank` (NEW)
```sql
CREATE TABLE question_bank (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(10) UNIQUE,  -- 'q1_1', 'q1_2', etc.
    category_id INTEGER,              -- 1-6
    category_name_ar VARCHAR(100),    -- 'مهارات التواصل', etc.
    category_stage VARCHAR(50),       -- 'communication', 'learning', etc.
    question_text_ar TEXT,
    question_text_en TEXT,
    weight DECIMAL(3,2),
    is_active BOOLEAN DEFAULT TRUE
);
```

**16 questions exist across 6 categories**:
1. Communication (3 questions)
2. Learning (3 questions)
3. Stability (3 questions)
4. Credibility (3 questions)
5. Adaptability (2 questions)
6. Field Knowledge (2 questions)

**Test candidate exists**:
- UUID: `aaaaaaaa-bbbb-cccc-dddd-111111111111`
- Name: أحمد علي الخباز
- Role: خباز (Baker)
- Has field experience: 'نعم' (NOT True)
- Smoker: 'لا' (NOT False)

---

## 🎯 YOUR TASKS

### ✅ TASK 1: Replace Candidate Models (COMPLETE FILE REPLACEMENT)

**File**: `backend/app/models/candidate.py`

**Action**: Replace ENTIRE file with the following code:

```python
# =============================================================================
# CANDIDATE MODELS - ARABIC-FIRST SCHEMA
# backend/app/models/candidate.py
# =============================================================================

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID


class CandidateRegistrationForm(BaseModel):
    """
    Registration form model - Arabic-first schema
    """
    # Personal Information
    full_name: str = Field(..., min_length=3, max_length=255)
    phone_number: str = Field(..., pattern=r'^07[0-9]{8}$')
    email: Optional[str] = None
    detailed_residence: Optional[str] = None
    
    # Job Application
    target_role: str = Field(..., description="Must be bakery-related role")
    expected_salary: Optional[int] = Field(None, ge=200, le=2000)
    years_of_experience: int = Field(default=0, ge=0, le=50)
    
    # Demographics (Arabic values)
    date_of_birth: Optional[date] = None
    gender: str = Field(..., pattern=r'^(ذكر|انثى)$')
    age_range: Optional[str] = Field(None, pattern=r'^(18-21|22-25|26 فأكثر)$')
    nationality: str = Field(default='اردني')
    marital_status: Optional[str] = Field(None, pattern=r'^(اعزب|متزوج|مطلق|ارمل)$')
    
    # Work Preferences
    preferred_schedule: Optional[str] = None
    can_start_immediately: Optional[str] = None
    proximity_to_branch: Optional[str] = None
    
    # Background (Arabic: نعم/لا - NOT boolean!)
    has_field_experience: str = Field(..., pattern=r'^(نعم|لا)$')
    previously_at_qabalan: str = Field(default='لا', pattern=r'^(نعم|لا)$')
    has_relatives_at_company: Optional[str] = Field(None, pattern=r'^(نعم|لا)$')
    
    # Education
    academic_status: Optional[str] = None
    
    # Cultural/Behavioral (Arabic)
    prayer_regularity: Optional[str] = None
    is_smoker: Optional[str] = Field(None, pattern=r'^(نعم|لا)$')
    grooming_objection: Optional[str] = None
    social_security_issues: Optional[str] = Field(default='لا', pattern=r'^(نعم|لا)$')
    
    @validator('target_role')
    def validate_bakery_role(cls, v):
        """Ensure role is bakery-related"""
        valid_roles = [
            'خباز', 'موظف مبيعات في المعرض', 'سائق توصيل',
            'عامل نظافة', 'تعبئة وتغليف', 'كاشير', 'مدير فرع',
            'مساعد خباز', 'عامل مستودعات'
        ]
        if v not in valid_roles:
            raise ValueError(f'Role must be bakery-related. Got: {v}')
        return v


class CandidateResponse(BaseModel):
    """Response model for candidate data"""
    id: UUID
    full_name: str
    phone_number: str
    email: Optional[str]
    target_role: str
    years_of_experience: int
    expected_salary: Optional[int]
    has_field_experience: str  # Arabic: 'نعم' or 'لا'
    proximity_to_branch: Optional[str]
    can_start_immediately: Optional[str]
    academic_status: Optional[str]
    gender: str
    marital_status: Optional[str]
    interview_count: int
    last_interview_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CandidateContract(BaseModel):
    """
    Immutable contract for interview session
    Updated for Arabic-first schema
    """
    candidate_id: UUID
    interview_id: UUID
    
    # Core Facts (IMMUTABLE)
    full_name: str
    target_role: str
    years_of_experience: int
    expected_salary: Optional[int]
    has_field_experience: str  # 'نعم' or 'لا'
    
    # Additional Context
    proximity_to_branch: Optional[str]
    can_start_immediately: Optional[str]
    academic_status: Optional[str]
    
    # Metadata
    contract_created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        frozen = True  # Immutable
    
    def get_experience_arabic(self) -> str:
        """Get experience in natural Arabic"""
        years = self.years_of_experience
        if years == 0:
            return "بدون خبرة"
        elif years == 1:
            return "سنة واحدة"
        elif years == 2:
            return "سنتين"
        elif 3 <= years <= 10:
            return f"{years} سنوات"
        else:
            return f"{years} سنة"
    
    def has_field_experience_bool(self) -> bool:
        """Convert Arabic yes/no to boolean"""
        return self.has_field_experience == 'نعم'


# Question Bank Models
class QuestionBankEntry(BaseModel):
    """Model for question bank entry"""
    id: int
    question_id: str
    category_id: int
    category_name_ar: str
    category_name_en: str
    category_stage: str
    question_text_ar: str
    question_text_en: Optional[str]
    weight: float
    is_active: bool
    display_order: Optional[int]
    
    class Config:
        from_attributes = True


class SelectedQuestion(BaseModel):
    """Model for a selected question during interview"""
    question_id: str
    question_text_ar: str
    category_id: int
    category_name_ar: str
    category_stage: str


# Interview Models
class InterviewUpdate(BaseModel):
    """Model for updating interview progress"""
    status: Optional[str] = None
    current_stage: Optional[str] = None
    categories_completed: Optional[int] = None
    current_category_index: Optional[int] = None
    asked_question_ids: Optional[List[str]] = None
    full_transcript: Optional[List[Dict]] = None
    detected_inconsistencies: Optional[List[Dict]] = None
```

---

### ✅ TASK 2: Create Database Question Selector Service (NEW FILE)

**File**: `backend/app/services/question_selector.py`

**Action**: CREATE this new file:

```python
# =============================================================================
# DATABASE QUESTION SELECTOR SERVICE
# backend/app/services/question_selector.py
# =============================================================================

from typing import List, Dict, Optional
import random
import logging
from supabase import Client

logger = logging.getLogger(__name__)


class DatabaseQuestionSelector:
    """
    Fetches questions from database question_bank table
    Replaces hardcoded question lists
    """
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self._category_cache = None
    
    def get_total_categories(self) -> int:
        """Get total number of active categories (should be 6)"""
        try:
            result = self.supabase.table("question_bank")\
                .select("category_id")\
                .eq("is_active", True)\
                .execute()
            
            if result.data:
                unique_categories = set(q['category_id'] for q in result.data)
                return len(unique_categories)
            return 6  # Fallback
        except Exception as e:
            logger.error(f"Error fetching category count: {e}")
            return 6
    
    def get_all_categories(self) -> List[Dict]:
        """Fetch all interview categories with metadata"""
        if self._category_cache:
            return self._category_cache
        
        try:
            result = self.supabase.table("question_bank")\
                .select("category_id, category_name_ar, category_name_en, category_stage")\
                .eq("is_active", True)\
                .execute()
            
            if result.data:
                # Group by category_id
                categories_dict = {}
                for row in result.data:
                    cat_id = row['category_id']
                    if cat_id not in categories_dict:
                        categories_dict[cat_id] = {
                            'category_id': cat_id,
                            'category_name_ar': row['category_name_ar'],
                            'category_name_en': row['category_name_en'],
                            'category_stage': row['category_stage']
                        }
                
                # Sort by category_id
                self._category_cache = sorted(categories_dict.values(), key=lambda x: x['category_id'])
                return self._category_cache
            
            return []
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []
    
    def get_category_by_index(self, category_index: int) -> Optional[Dict]:
        """Get category by index (0-based)"""
        categories = self.get_all_categories()
        if 0 <= category_index < len(categories):
            return categories[category_index]
        return None
    
    def select_random_question(
        self,
        category_id: int,
        exclude_ids: List[str] = None
    ) -> Optional[Dict]:
        """
        Select random question from category
        
        Args:
            category_id: Category ID (1-6)
            exclude_ids: List of question IDs already asked
        
        Returns:
            Question dict or None
        """
        try:
            # Fetch all questions for this category
            query = self.supabase.table("question_bank")\
                .select("*")\
                .eq("category_id", category_id)\
                .eq("is_active", True)\
                .order("display_order")
            
            result = query.execute()
            
            if not result.data:
                logger.warning(f"No questions found for category {category_id}")
                return None
            
            # Filter excluded
            exclude_ids = exclude_ids or []
            available = [q for q in result.data if q['question_id'] not in exclude_ids]
            
            if not available:
                logger.info(f"All questions used in category {category_id}, resetting pool")
                available = result.data
            
            # Random selection
            selected = random.choice(available)
            
            logger.info(f"📝 Selected Q{selected['question_id']} from category {category_id}")
            
            return {
                "question_id": selected["question_id"],
                "question_text_ar": selected["question_text_ar"],
                "question_text_en": selected.get("question_text_en"),
                "category_id": selected["category_id"],
                "category_name_ar": selected["category_name_ar"],
                "category_name_en": selected["category_name_en"],
                "category_stage": selected["category_stage"],
                "weight": selected["weight"]
            }
        except Exception as e:
            logger.error(f"Error selecting question: {e}")
            return None
    
    def get_category_name(self, category_index: int) -> str:
        """Get Arabic category name by index"""
        category = self.get_category_by_index(category_index)
        return category["category_name_ar"] if category else "Unknown"
```

---

### ✅ TASK 3: Update Interview Agent (PARTIAL FILE UPDATE)

**File**: `backend/app/core/interview_agent.py`

**Action**: UPDATE the following specific sections:

#### 3.1: Add Import at Top of File
```python
# Add these imports at the top
from app.services.question_selector import DatabaseQuestionSelector
from app.db.supabase_client import get_supabase_client
```

#### 3.2: Update `__init__` Method
Find the `__init__` method and UPDATE it to:

```python
def __init__(self):
    """
    Initialize interview agent with database question selector
    """
    from app.core.llm_manager import MultiProviderLLM
    
    self.llm = MultiProviderLLM()
    self.temperature = 0.2
    
    # Initialize database question selector
    self.supabase = get_supabase_client()
    self.question_selector = DatabaseQuestionSelector(self.supabase)
    
    # Build state machine
    self.workflow = self._build_workflow()
    
    logger.info("✅ InterviewAgent initialized with database question selector")
```

#### 3.3: Replace `_select_question_node` Method
Find and REPLACE the entire `_select_question_node` method with:

```python
def _select_question_node(self, state: InterviewState) -> InterviewState:
    """
    Node: Select next question from DATABASE
    
    UPDATED: Fetches from Supabase question_bank table
    """
    current_stage = state["current_stage"]
    
    # Only select questions during "questioning" stage
    if current_stage != "questioning":
        logger.info(f"Stage '{current_stage}' - skipping question selection")
        return state
    
    # Get current category index (0-5)
    category_index = state.get("current_category_index", 0)
    
    # Check if all categories completed
    total_categories = self.question_selector.get_total_categories()
    
    if category_index >= total_categories:
        logger.info("✅ All categories completed - moving to closing")
        state["current_stage"] = "closing"
        return state
    
    # Convert category_index (0-5) to category_id (1-6)
    category_id = category_index + 1
    
    # Get excluded question IDs
    asked_ids = state.get("asked_question_ids", [])
    
    # Select random question from DATABASE
    selected = self.question_selector.select_random_question(
        category_id=category_id,
        exclude_ids=asked_ids
    )
    
    if selected:
        logger.info(f"📝 DATABASE: Category {category_id} - {selected['category_name_ar']}")
        logger.info(f"   Question: {selected['question_text_ar'][:50]}...")
        
        # Update state
        state["selected_question_id"] = selected["question_id"]
        state["selected_question_text"] = selected["question_text_ar"]
        state["selected_question_category"] = selected["category_name_ar"]
        state["selected_question_stage"] = selected["category_stage"]
        
        # Track asked questions
        if "asked_question_ids" not in state:
            state["asked_question_ids"] = []
        state["asked_question_ids"].append(selected["question_id"])
    else:
        logger.error(f"❌ Failed to select question for category {category_id}")
        state["current_category_index"] = category_index + 1
    
    return state
```

#### 3.4: Replace `_build_system_prompt` Method
Find and REPLACE the entire `_build_system_prompt` method with:

```python
def _build_system_prompt(
    self,
    contract,
    stage: str,
    selected_question: Optional[str] = None,
    category_name: Optional[str] = None
) -> str:
    """
    Build system prompt with Jordanian dialect enforcement
    
    UPDATED: Enhanced dialect rules and examples
    """
    
    # Get experience in Arabic
    experience_ar = contract.get_experience_arabic()
    field_exp_ar = "عنده خبرة" if contract.has_field_experience_bool() else "بدون خبرة"
    
    # Base persona with STRONG Jordanian dialect rules
    base_prompt = f"""# هويتك
أنت سارة، مسؤولة توظيف في مخبز Golden Crust (قبلان للصناعات الغذائية).

# حقائق المتقدم (من قاعدة البيانات - ثابتة)
⚠️ استخدم هذه الحقائق بالضبط:

- الاسم: {contract.full_name}
- الوظيفة المطلوبة: {contract.target_role}
- عدد سنوات الخبرة: {experience_ar} ({contract.years_of_experience} سنة بالضبط)
- الراتب المتوقع: {contract.expected_salary} دينار
- خبرة بالمجال: {field_exp_ar}
- قرب السكن: {contract.proximity_to_branch or "غير محدد"}

# قواعد اللهجة الأردنية (MANDATORY)
**يجب استخدام اللهجة الأردنية (عمّان) فقط:**

❌ ممنوع تقول:
- ماذا → استخدم: شو
- لماذا → استخدم: ليش
- أين → استخدم: وين
- كيف حالك → استخدم: كيفك
- سوف → استخدم: راح
- أريد → استخدم: بدي
- لديك → استخدم: عندك
- الآن → استخدم: هسا
- هذا → استخدم: هاد
- جيد → استخدم: منيح
- كثيراً → استخدم: كتير

✅ أمثلة صحيحة:
- "شو بتعمل بوقت فراغك؟"
- "ليش بدك تشتغل معنا؟"
- "كيفك اليوم؟"
- "راح أسألك شوية أسئلة"
- "عندك خبرة بهاد المجال؟"

# قواعد عامة
1. الردود قصيرة: 15-20 كلمة
2. سؤال واحد فقط
3. استخدم رقم الخبرة الدقيق: {contract.years_of_experience} سنة
4. ممنوع الإنجليزية نهائياً
"""
    
    # Stage-specific prompts
    if stage == "opening":
        return base_prompt + f"""
# المرحلة: الترحيب

رحّب بالمتقدم بشكل دافئ واحترافي بلهجة أردنية.

**مثال**:
"مرحباً {contract.full_name}! أنا سارة من مخبز Golden Crust. كيفك اليوم؟ مستعد نبدأ؟"

خليك دافئ ومحترف. استخدم اللهجة الأردنية.
"""
    
    elif stage == "questioning" and selected_question:
        return base_prompt + f"""
# المرحلة: الأسئلة - {category_name}

**السؤال من بنك الأسئلة**:
"{selected_question}"

**مهمتك**:
اطرح هذا السؤال بطريقة طبيعية بلهجة أردنية.

**أمثلة تكييف**:

السؤال: "كيف تتعامل مع زميل عمل يسيء فهمك؟"
تكييف: "بالشغل، شو بتسوي لما زميلك يفهمك غلط؟"

السؤال: "حدثني عن خطأ ارتكبته في عملك السابق"
تكييف: "انت عندك {experience_ar} خبرة، حكيلي عن موقف غلطت فيه وشو تعلمت منه؟"

**الآن اطرح السؤال بلهجة أردنية طبيعية.**
"""
    
    elif stage == "closing":
        return base_prompt + f"""
# المرحلة: الاختتام

اشكر المتقدم واخبره الخطوات التالية.

**مثال**:
"تمام {contract.full_name}، شكراً كتير على وقتك! راح نتواصل معك خلال أسبوع. عندك أي سؤال؟"

اختم بشكل محترم ودافئ بلهجة أردنية.
"""
    
    return base_prompt
```

#### 3.5: Update `_generate_response_node` Method
Find where the system prompt is built and UPDATE to pass selected question:

Look for this line:
```python
system_prompt = self._build_system_prompt(contract, current_stage)
```

REPLACE with:
```python
# Get selected question if in questioning stage
selected_question = state.get("selected_question_text")
category_name = state.get("selected_question_category")

system_prompt = self._build_system_prompt(
    contract,
    current_stage,
    selected_question=selected_question,
    category_name=category_name
)
```

---

### ✅ TASK 4: Create Test Files (NEW FILES)

#### 4.1: Database Connection Test

**File**: `backend/test_database.py`

```python
"""Test database connection and question fetching"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.supabase_client import get_supabase_client
from app.services.question_selector import DatabaseQuestionSelector

def main():
    print("🧪 Testing Database Connection...")
    print("=" * 60)
    
    # Test Supabase connection
    try:
        supabase = get_supabase_client()
        print("✅ Supabase connected")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return
    
    # Test question selector
    try:
        selector = DatabaseQuestionSelector(supabase)
        print("✅ Question selector initialized")
    except Exception as e:
        print(f"❌ Question selector failed: {e}")
        return
    
    # Get all categories
    print("\n" + "=" * 60)
    print("📊 Categories in Database:")
    print("=" * 60)
    
    categories = selector.get_all_categories()
    print(f"Total categories: {len(categories)}")
    
    for cat in categories:
        print(f"\n  {cat['category_id']}. {cat['category_name_ar']}")
        print(f"     English: {cat['category_name_en']}")
        print(f"     Stage: {cat['category_stage']}")
    
    # Test random question selection
    print("\n" + "=" * 60)
    print("🎲 Testing Random Question Selection:")
    print("=" * 60)
    
    for category_id in range(1, 7):
        question = selector.select_random_question(category_id=category_id)
        if question:
            print(f"\nCategory {category_id}: {question['category_name_ar']}")
            print(f"  ID: {question['question_id']}")
            print(f"  Q: {question['question_text_ar'][:60]}...")
        else:
            print(f"\n❌ No question found for category {category_id}")
    
    # Test candidate fetch with Arabic values
    print("\n" + "=" * 60)
    print("👤 Testing Candidate Fetch (Arabic Values):")
    print("=" * 60)
    
    try:
        result = supabase.table("candidates")\
            .select("*")\
            .eq("id", "aaaaaaaa-bbbb-cccc-dddd-111111111111")\
            .execute()
        
        if result.data:
            candidate = result.data[0]
            print(f"✅ Candidate: {candidate['full_name']}")
            print(f"   Role: {candidate['target_role']}")
            print(f"   Experience: {candidate['years_of_experience']} years")
            print(f"   Has field exp: '{candidate['has_field_experience']}' (Arabic)")
            print(f"   Smoker: '{candidate['is_smoker']}' (Arabic)")
            
            # Validate Arabic values
            assert candidate['has_field_experience'] in ['نعم', 'لا'], "Must be Arabic!"
            assert candidate['is_smoker'] in ['نعم', 'لا'], "Must be Arabic!"
            
            print("\n✅ All Arabic validations passed!")
        else:
            print("❌ Test candidate not found")
    except Exception as e:
        print(f"❌ Candidate fetch failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 All database tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

#### 4.2: Contract Test

**File**: `backend/test_contract.py`

```python
"""Test CandidateContract with Arabic values"""
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent))

from app.models.candidate import CandidateContract

def main():
    print("🧪 Testing CandidateContract...")
    print("=" * 60)
    
    # Create contract with Arabic values
    try:
        contract = CandidateContract(
            candidate_id=UUID("aaaaaaaa-bbbb-cccc-dddd-111111111111"),
            interview_id=UUID("bbbbbbbb-cccc-dddd-eeee-222222222222"),
            full_name="أحمد علي الخباز",
            target_role="خباز",
            years_of_experience=10,
            expected_salary=450,
            has_field_experience='نعم',  # Arabic!
            proximity_to_branch='قريب بنفس المنطقة واحضر مواصلات',
            can_start_immediately='نعم استطيع',
            academic_status='انتهيت من المسيرة الدراسية (ثانوية عامة)'
        )
        print("✅ Contract created successfully")
    except Exception as e:
        print(f"❌ Contract creation failed: {e}")
        return
    
    # Test fields
    print(f"\n📋 Contract Fields:")
    print(f"   Name: {contract.full_name}")
    print(f"   Role: {contract.target_role}")
    print(f"   Experience (raw): {contract.years_of_experience}")
    print(f"   Experience (Arabic): {contract.get_experience_arabic()}")
    print(f"   Has field exp (string): {contract.has_field_experience}")
    print(f"   Has field exp (bool): {contract.has_field_experience_bool()}")
    
    # Test immutability
    print(f"\n🔒 Testing Immutability:")
    try:
        contract.years_of_experience = 5
        print("❌ Contract is NOT immutable!")
    except:
        print("✅ Contract is immutable (as expected)")
    
    # Test Arabic conversion helper
    print(f"\n🔄 Testing Arabic Helpers:")
    print(f"   'نعم' → {contract.has_field_experience_bool()}")
    
    test_contract_2 = CandidateContract(
        candidate_id=UUID("aaaaaaaa-bbbb-cccc-dddd-111111111111"),
        interview_id=UUID("bbbbbbbb-cccc-dddd-eeee-222222222222"),
        full_name="Test",
        target_role="خباز",
        years_of_experience=5,
        expected_salary=400,
        has_field_experience='لا'  # No
    )
    print(f"   'لا' → {test_contract_2.has_field_experience_bool()}")
    
    print("\n" + "=" * 60)
    print("🎉 All contract tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

---

## 🎯 CRITICAL REQUIREMENTS

### ⚠️ DO NOT MODIFY THESE FILES
These files are working perfectly. **DO NOT TOUCH**:
- ❌ `app/services/groq_transcriber.py` - STT is perfect
- ❌ `app/services/elevenlabs_tts.py` - TTS is working
- ❌ `app/core/llm_manager.py` - Multi-provider LLM stable
- ❌ `app/api/websocket/interview_ws.py` - WebSocket good
- ❌ `app/core/persona_enforcer.py` - Already has dialect rules

### ✅ ONLY MODIFY THESE FILES
- ✅ `app/models/candidate.py` - REPLACE ENTIRE FILE
- ✅ `app/services/question_selector.py` - CREATE NEW FILE
- ✅ `app/core/interview_agent.py` - UPDATE 5 SPECIFIC SECTIONS
- ✅ `test_database.py` - CREATE NEW FILE
- ✅ `test_contract.py` - CREATE NEW FILE

---

## 🧪 TESTING PROCEDURE

After completing all tasks, run these tests:

### Test 1: Database Connection
```bash
cd backend
python test_database.py
```

**Expected Output**:
```
✅ Supabase connected
✅ Question selector initialized
Total categories: 6
  1. مهارات التواصل
  2. القدرة على التعلم
  ...
✅ All Arabic validations passed!
```

### Test 2: Contract
```bash
python test_contract.py
```

**Expected Output**:
```
✅ Contract created successfully
✅ Contract is immutable
🎉 All contract tests passed!
```

### Test 3: Start Backend
```bash
uvicorn app.main:app --reload --port 8001
```

**Expected**: No import errors, server starts successfully

### Test 4: Interview Test
Visit: `http://localhost:3000/interview/aaaaaaaa-bbbb-cccc-dddd-111111111111`

**Expected Flow**:
```
Turn 1: "مرحباً أحمد! كيفك اليوم؟" (Jordanian)
Turn 2: "شو بتسوي لما زميلك يفهمك غلط؟" (Question from DB)
Turn 3: [user responds]
Turn 4: Next category question...
...6 categories total...
Final: "شكراً كتير على وقتك!"
```

---

## ✅ SUCCESS CHECKLIST

After implementation:

```
□ No import errors when starting backend
□ test_database.py shows 6 categories
□ test_contract.py passes all tests
□ Interview fetches questions from database
□ Sarah speaks pure Jordanian ("شو" not "ماذا")
□ All 6 categories asked in sequence
□ No type errors (boolean/string conflicts)
□ Interview saves to database correctly
```

---

## 📊 EXPECTED CHANGES SUMMARY

| File | Action | Lines Changed |
|------|--------|---------------|
| models/candidate.py | Replace entire file | ~200 |
| services/question_selector.py | Create new file | ~150 |
| interview_agent.py | Update 5 sections | ~100 |
| test_database.py | Create new file | ~100 |
| test_contract.py | Create new file | ~80 |

**Total**: ~630 lines of production-ready code

---

## 🎉 FINAL NOTES

1. **Database Already Set Up**: User has run SQL reset script
2. **Test Candidate Exists**: Ahmad the Baker (UUID: aaaaaaaa-bbbb-cccc-dddd-111111111111)
3. **16 Questions in DB**: Across 6 categories
4. **Arabic Schema**: All yes/no fields use 'نعم'/'لا'
5. **Jordanian Dialect**: System prompts enforce natural Amman Arabic

**Start with Task 1** and work sequentially through Task 4. Test after each major change.

**Estimated Time**: 45-60 minutes for complete implementation.

---

Execute these tasks carefully. Report any errors. The goal is a production-ready Arabic-first system with database-driven questions and natural Jordanian dialect.
