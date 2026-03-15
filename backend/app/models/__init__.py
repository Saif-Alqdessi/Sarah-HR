from app.models.candidate import (
    CandidateRegistrationForm,
    CandidateContract,
    CandidateResponse,
    QuestionBankEntry,
    SelectedQuestion,
    InterviewUpdate,
)
from app.models.interview import InterviewCreate, Interview
from app.models.score import ScoreCreate, Score

# Backward-compatibility aliases for old code that imports the deleted names
CandidateCreate = CandidateRegistrationForm
Candidate = CandidateResponse

__all__ = [
    # New Arabic-first models
    "CandidateRegistrationForm",
    "CandidateContract",
    "CandidateResponse",
    "QuestionBankEntry",
    "SelectedQuestion",
    "InterviewUpdate",
    # Legacy aliases
    "CandidateCreate",
    "Candidate",
    # Other models
    "InterviewCreate",
    "Interview",
    "ScoreCreate",
    "Score",
]
