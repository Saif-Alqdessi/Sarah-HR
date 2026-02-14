from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats():
    return {"total_candidates": 0, "completed_interviews": 0}


@router.get("/by-role")
async def get_analytics_by_role():
    return {"roles": []}
