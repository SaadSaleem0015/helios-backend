from ast import Dict
from collections import defaultdict
import datetime
from fastapi import APIRouter, Depends, Query
from typing import Annotated
from models.user import User
from datetime import datetime, timedelta

from models.lead import Lead
from models.file import File
from models.assistant import Assistant
from helpers.jwt_token import get_admin

admin_statistics_router = APIRouter()

@admin_statistics_router.get("/admin/statistics")
async def admin_stats(user: Annotated[User, Depends(get_admin)]):
    return{
        "leads": await Lead.filter().count(),
        "files": await File.filter().count(),
        "users": await User.filter().count(),
        "assistants": await Assistant.filter().count()
    }

@admin_statistics_router.get("/admin/users-stats")
async def admin_stats(
    user: Annotated[User, Depends(get_admin)],
    period: str = Query("30d", description="Time period: 30d, 3m, 6m"),
):
    today = datetime.utcnow()

    if period == "3m":
        start_date = today - timedelta(days=90)
    elif period == "6m":
        start_date = today - timedelta(days=180)
    else:
        start_date = today - timedelta(days=30)

    users = await User.filter(created_at__gte=start_date).values("created_at")

    user_counts: Dict[str, int] = defaultdict(int)
    for user in users:
        date_str = user["created_at"].strftime("%Y-%m-%d") 
        user_counts[date_str] += 1

    return [{"date": date, "count": count} for date, count in sorted(user_counts.items())]
