from fastapi import HTTPException
from tortoise.functions import Sum
from models.call_log import CallLog
from models.user import User

async def get_total_call_duration(user_id):
    try:
        result = await CallLog.filter(
            user_id=user_id  
        ).annotate(
            total_duration=Sum('call_duration')
        ).values('total_duration')

        if result and result[0]['total_duration'] is not None:
            return int(result[0]['total_duration'])
        return 0
    except Exception as e:
        print(f"Error getting call duration: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to calculate call duration: {str(e)}"
        )