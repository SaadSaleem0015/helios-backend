from typing import Annotated
from fastapi import APIRouter, Depends,HTTPException
from helpers.jwt_token import get_admin
from models.assistant import Assistant
from models.call_log import CallLog
from models.defaultSettings import DefaultSettings
from models.purchased_number import PurchasedNumber
from models.spent import Spent
from models.super_admin_setting import SuperAdminSetting
from models.user import User
from datetime import datetime, timedelta, timezone
from tortoise.functions import Sum
from pydantic import BaseModel
from models.payment import Payment
from models.timeLimit import TimeLimit
from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
from datetime import datetime, timedelta
import pytz
from pydantic import BaseModel



admin_router = APIRouter()

class FilterData(BaseModel):
    user_id: int
    start_date: str = None
    end_date: str = None


class GrantMinutesPayload(BaseModel):
    minutes: float
   

async def check_balance(user_id: int) -> bool:
    total_amount_paid = await Payment.filter(user_id=user_id).annotate(
        total_paid=Sum("amount_paid")
    ).values("total_paid")

    total_cost = await Spent.filter(user_id=user_id).annotate(
        total_cost=Sum("spent_money")
    ).values("total_cost")

    total_amount_paid = total_amount_paid[0]["total_paid"] if total_amount_paid and total_amount_paid[0]["total_paid"] is not None else 0
    total_cost = total_cost[0]["total_cost"] if total_cost and total_cost[0]["total_cost"] is not None else 0

    total_amount_paid = float(total_amount_paid)
    total_cost = float(total_cost)

    balance = total_amount_paid - total_cost
    return balance 

@admin_router.get("/users")
async def get_logs(admin: Annotated[User, Depends(get_admin)]):
    users = await User.filter(type = "user").first("-id").all()

    result = []
    for user in users:
        print(user.id)
   
        balance = await check_balance(user.id) if user else 0
        result.append({
                "id": user.id,
                "name": user.name if user else '',
                "email":user.email if user else '',
                "balance": balance,
                "phone": user.phone if user else '',
                "is_active": user.is_active if user  else False,
              
            })

    return result
@admin_router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: int,
    admin: Annotated[User, Depends(get_admin)]
):
    # Find user
    user = await User.filter(id=user_id, type="user").first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Toggle status
    user.is_active = not user.is_active
    await user.save()

    return {
        "success": True,
        "message": f"User has been {'activated' if user.is_active else 'deactivated'} successfully.",
        "user_id": user.id,
        "is_active": user.is_active
    }

@admin_router.put("/user/{userId}/live")
async def live_account(userId: int,user: Annotated[User, Depends(get_admin)]):
    try:
        user = await User.filter(id=userId).first()
        user.is_active = True
        await user.save()
        # await Logs.create(
        #         user = user,
        #         message = f"is live now.",
        #         short_message = "deactivate_user"
        #     )
        return {"success": True, "detail": "Account is live now."}
    except:
        raise HTTPException(status_code=404, detail="User not found.")
    
@admin_router.put("/user/{userId}/suspend")
async def suspend_account(userId: int,user: Annotated[User, Depends(get_admin)]):
    try:
        user = await User.filter(id=userId, main_admin = True).first()
        user.is_active = False
        await user.save()
        # await Logs.create(
        #         user = user,
        #         message = f"is live now.",
        #         short_message = "deactivate_user"
        #     )
        return {"success": True, "detail": "Account is suspended."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{e}")

@admin_router.get("/user/{userId}/assistants")
async def get_assistants_by_user(userId: int,user: Annotated[User , Depends(get_admin)]):
    try:
        assistants = await Assistant.filter(user_id=userId).all()
        return {"assistants":assistants}

    except:
        raise HTTPException(status_code=404, detail="User not found")
    
@admin_router.put("/user-grant-minutes/{userId}")
async def update_assistants_by_user(userId: int,data:GrantMinutesPayload,user: Annotated[User , Depends(get_admin)]):
    try:
        admin = await User.filter(id=userId).first()
        time_limit = await TimeLimit.filter(user=admin).first()
        if time_limit:
            time_limit.seconds = data.minutes*60 +time_limit.seconds
            await time_limit.save()
        else:
            await TimeLimit.create(
                seconds= data.minutes*60,
                user= admin
            )

        return {"success":True ,  "detail": "Minutes granted successfully"}

    except Exception as e :
        raise HTTPException(status_code=404, detail=f"server error {e}")
    


      
@admin_router.get("/user/{userId}/call-logs")
async def get_call_logs_by_user(userId: int,user: Annotated[User , Depends(get_admin)]):
    try:    
        call_logs = await CallLog.filter(user__id=userId).all()
        return {"call_logs":call_logs}
    except :
        raise HTTPException(status_code=404, detail="User not found")
    
@admin_router.get("/user/{userId}/phone-numbers")
async def get_phone_numbers_by_user(userId: int,user: Annotated[User , Depends(get_admin)]):
    try:
        phone_numbers = await PurchasedNumber.filter(user__id=userId).all()
        return {"phone_numbers" : phone_numbers}
    except :
        raise HTTPException(status_code=404, detail="User not found")
    

# @admin_router.post("/filter-company-call-logs")
# async def get_call_logs_by_company(filter_data: FilterData, user: Annotated[User , Depends(get_admin)]):
#     try:
#         company = await Company.get(id=filter_data.company_id)
#         call_logs_query = CallLog.filter(user__company=company)

#         start_date = datetime.fromisoformat(filter_data.start_date.replace("Z", "+00:00")) if filter_data.start_date else None
#         end_date = datetime.fromisoformat(filter_data.end_date.replace("Z", "+00:00")) if filter_data.end_date else None
        
#         if start_date:
#             call_logs_query = call_logs_query.filter(call_started_at__gte=start_date)

#         if end_date:
#             call_logs_query = call_logs_query.filter(call_started_at__lte = end_date)
        
#         logs = await call_logs_query.all()
#         return logs

#     except Exception as e:
#         print("Error", e)   
#         raise HTTPException(status_code=404, detail="Company not found or error occurred")



@admin_router.get("/pnl-report")
async def mdaily_report(
    timeframe: str, 
    user: Annotated[User, Depends(get_admin)], 
    startDate: str = None, 
    endDate: str = None
):
    print(f"Received timeframe: {timeframe}")
    print(f"Received startDate: {startDate}")
    print(f"Received endDate: {endDate}")

    start_date, end_date = get_timeframe_dates(timeframe, startDate, endDate)
    print("Start Date (after parsing):", start_date)
    print("End Date (after parsing):", end_date)

    users = await User.filter(type="user").all().prefetch_related('payments', 'call_log')

    response = []
    for single_user in users:
        paid_sum = 0
        received_sum = 0
        call_log_cost = 0
        minutes_used = 0
        user_name = None
        calls_made = 0
        transfer_made = 0
        
        for single_payment in single_user.payments:
            payment_date = single_payment.created_at 
            if start_date <= payment_date <= end_date:
                paid_sum += single_payment.amount_paid
                received_sum += single_payment.amount_received

        for single_call_log in single_user.call_log:
            call_log_date = single_call_log.call_started_at  
            if start_date <= call_log_date <= end_date:
                call_log_cost += single_call_log.cost or 0
                minutes_used += getattr(single_call_log, 'call_duration', 0) or 0
                calls_made += 1
                if single_call_log.is_transferred is True:
                    transfer_made += 1

     

        response.append({
            **dict(single_user), 
            "paid_sum": paid_sum,
            "received_sum": received_sum,
            "call_log_cost": call_log_cost,
            "company_name": single_user.name,
            "minutes_used": minutes_used,
            "calls_made": calls_made,
            "transfer_made": transfer_made
        })

    return response


@admin_router.get("/user-pnl-report/{userId}")
async def mdaily_report(
    timeframe: str, 
    userId : int,
    admin: Annotated[User, Depends(get_admin)], 
    startDate: str = None, 
    endDate: str = None
):
    user = await User.filter(id = userId).first()
    start_date, end_date = get_timeframe_dates(timeframe, startDate, endDate)
    # main_admin = await User.filter(company_id = company_id , main_admin = True).first()
    # if not main_admin:
    #     return {"message": "No user found for the given company ID."}
    company_call_logs = await CallLog.filter(user = user)
    company_payments = await Payment.filter(user = user)
    vv_settings = await SuperAdminSetting.filter(user = user).first()
    default_setting = await DefaultSettings.first()
    paid_sum = 0
    received_sum = 0
    call_log_cost = 0
    minutes_used = 0
    company_name = user.name if user else "Unknown"
    calls_made = 0
    transfer_made = 0
    
    for single_payment in company_payments:
        print("single", single_payment.amount_paid)
        payment_date = single_payment.created_at 
        if start_date <= payment_date <= end_date:
            paid_sum += single_payment.amount_paid
            received_sum += single_payment.amount_received

    for single_call_log in company_call_logs:
        print("7890987890")
        call_log_date = single_call_log.call_started_at  
        if start_date <= call_log_date <= end_date:
            call_log_cost += single_call_log.cost or 0
            minutes_used += getattr(single_call_log, 'call_duration', 0) or 0
            calls_made += 1
            if single_call_log.is_transferred is True:
                transfer_made += 1
    transfer_rate = vv_settings.transfer_rate if vv_settings and hasattr(vv_settings, "transfer_rate") else (
        default_setting.transfer_rate if default_setting else 0
    )

    response = ({
        **dict(user), 
        "paid_sum": paid_sum,
        "received_sum": received_sum,
        "call_log_cost": call_log_cost,
        "company_name":company_name,
        "minutes_used": minutes_used,
        "calls_made": calls_made,
        "transfer_made": transfer_made,
        "transfer_rate" :transfer_rate
    })

    return response


def get_timeframe_dates(timeframe: str, start_date: str = None, end_date: str = None):
    if timeframe == "Today":
        end_date = datetime.utcnow().replace(tzinfo=timezone.utc, hour=23, minute=59, second=59, microsecond=999999)
        start_date = datetime.utcnow().replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "Last 7d":
        end_date = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=7)
    elif timeframe == "Last 14d":
        end_date = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=14)
    elif timeframe == "Last 30d":
        end_date = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=30)
    elif timeframe == "Last 60d":
        end_date = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=60)
    
    elif start_date and end_date:
        try:
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if isinstance(start_date, str) else start_date
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if isinstance(end_date, str) else end_date
        except ValueError as e:
            raise ValueError("Invalid date format. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ).") from e
    else:
        raise ValueError("Invalid timeframe or date range")

    return start_date, end_date




# class UpdateTrialRequest(BaseModel):
#     trial_end_date: str  

# @admin_router.get('/check_company_trial/{company_id}')
# async def check_company_trial_status(company_id: int):

#     try:
#         company = await Company.filter(id=company_id).first()
#         if not company:
#             raise HTTPException(status_code=404, detail="Company not found")
        
#         user = await User.filter(company_id=company_id).first()
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found for this company")
        
#         if user.has_active_subscription:
#             return {
#                 "success": True,
#                 "isInTrial": False ,
#                 "has_subscription":True
#             }
        
#         if user.free_trial_start is None:
#             return {
#                 "success": True,
#                 "isInTrial": False , 
#                 "has_subscription":False
#             }
        
#         if user.has_free_trial:
#             utc = pytz.UTC
#             free_trial_started = user.free_trial_start if user.free_trial_start.tzinfo else utc.localize(user.free_trial_start)
#             current_time = datetime.now(utc)
            
#             trial_end_date = free_trial_started + timedelta(days=14)
            
#             if current_time < trial_end_date:
#                 return {
#                     "success": True,
#                     "isInTrial": True ,
#                     "has_subscription":False
#                 }
#             else:
#                 user.has_free_trial = False
#                 await user.save()
                
#                 return {
#                     "success": True,
#                     "isInTrial": False,
#                     "has_subscription":False
#                 }
#         else:
#             return {
#                 "success": True,
#                 "isInTrial": False,
#                 "has_subscription":False
#             }
            
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# @admin_router.put('/update_company_trial/{company_id}')
# async def update_company_trial(company_id: int, request: UpdateTrialRequest):
#     try:
#         company = await Company.filter(id=company_id).first()
#         if not company:
#             raise HTTPException(status_code=404, detail="Company not found")
        
#         users_without_subscription = await User.filter(
#             company_id=company_id,
#             has_active_subscription=False
#         ).all()
        
#         if not users_without_subscription:
#             raise HTTPException(
#                 status_code=404, 
#                 detail="No users found for this company without active subscriptions"
#             )
        
#         try:
#             new_trial_end = datetime.fromisoformat(request.trial_end_date.replace('Z', '+00:00'))
#             if new_trial_end.tzinfo is None:
#                 new_trial_end = pytz.UTC.localize(new_trial_end)
#         except ValueError:
#             raise HTTPException(
#                 status_code=400, 
#                 detail="Invalid date format. Use ISO format like '2024-12-31' or '2024-12-31T23:59:59'"
#             )
        
#         trial_start_date = new_trial_end - timedelta(days=14)
        
#         updated_users = []
#         for user in users_without_subscription:
#             user.free_trial_start = trial_start_date
#             user.has_free_trial = True
#             await user.save()
            
#             updated_users.append({
#                 "user_id": user.id,
#                 "user_name": user.name,
#                 "user_email": user.email
#             })
        
#         days_remaining = (new_trial_end - datetime.now(pytz.UTC)).days
        
#         return {
#             "success": True,
#             "message": f"Trial updated successfully",
#             "company_id": company_id,
#             "company_name": company.company_name,
#             "trial_start_date": trial_start_date.isoformat(),
#             "trial_end_date": new_trial_end.isoformat(),
#             "days_remaining": max(0, days_remaining),
#             "updated_users_count": len(updated_users),
#             "updated_users": updated_users,
#             "is_trial_active": True
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")