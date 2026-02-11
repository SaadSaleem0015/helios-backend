import json
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, time, timedelta
import pytz
import requests
from helpers.criteria_check import has_payment_method
from helpers.vapi_helper import get_headers
from models.assistant import Assistant
from models.lead import Lead
from models.lead_status import LeadStatus
from models.schedule import Schedule
from models.schedule_time import ScheduleTime
from models.schedule_call import ScheduleCall
from models.user import User
from helpers.jwt_token import get_current_user, get_active_user
from helpers.SceduleCall import trigger_scheduled_call
schedule_router = APIRouter()


class ScheduleEntry(BaseModel):
    day: str
    start: str
    end: str

class Schedule_Call(BaseModel):
    title: str
    # vapi_assistant_id: str
    timeZone: str
    call_id: Optional[List[str]] = None
    status: Optional[str] = None
    schedule: Optional[List[ScheduleEntry]] = None

TIMEZONE_ALIASES = {
    "Central": "US/Central",
    "Eastern": "US/Eastern",
    "Pacific": "US/Pacific",
}

@schedule_router.post("/scheduled-call")
async def schedule_call(
    data: Schedule_Call,
    main_admin: Annotated[User, Depends(get_active_user)],
    user: User = Depends(get_active_user),
):
    payment_method = await has_payment_method(user)
    if not payment_method:
           return {
                "success":False,
                "detail": f"Unable to schedule call. You should have an active payment method first.",
            }
    if not data.schedule:
        raise HTTPException(status_code=400, detail="Schedule data is required.")
    
    # if data.timeZone not in pytz.all_timezones and data.timeZone not in TIMEZONE_ALIASES:
    #     raise HTTPException(status_code=400, detail="Invalid timezone provided.")
    user_timezone = TIMEZONE_ALIASES.get(data.timeZone, data.timeZone)
    
    valid_schedule = [
        entry for entry in data.schedule if entry.start and entry.end
    ]
    complete_valid_schedule = [
    {
        "day": entry.day,
        "start": entry.start,
        "end": entry.end,
    }
    for entry in data.schedule if entry.start and entry.end
]

    if not valid_schedule:
        raise HTTPException(
            status_code=400,
            detail="Invalid schedule. At least one valid entry with start and end times is required."
        )
    schedule_exists = await Schedule.filter(user = main_admin).first()
    if schedule_exists:
        raise HTTPException(
            status_code=400,
            detail="Schedule already created"
        )
    else:
        try:
            schedule = await Schedule.create(
                title=data.title,
                timezone=user_timezone,
                user=main_admin,
                complete_schedule = json.dumps(complete_valid_schedule)
            )

            for entry in valid_schedule:
                original_day = entry.day
                start_time_str = entry.start
                end_time_str = entry.end

                try:
                    user_tz = pytz.timezone(user_timezone)
                    start_time_local = datetime.strptime(start_time_str, "%H:%M").replace(tzinfo=user_tz)
                    end_time_local = datetime.strptime(end_time_str, "%H:%M").replace(tzinfo=user_tz)

                    # start_time_utc = start_time_local.astimezone(pytz.utc)
                    # end_time_utc = end_time_local.astimezone(pytz.utc)

                    # adjusted_day = original_day
                    # if start_time_utc.date() > start_time_local.date():
                    #     adjusted_day = (datetime.strptime(original_day, "%a") + timedelta(days=1)).strftime("%a").upper()
                    # elif start_time_utc.date() < start_time_local.date():
                    #     adjusted_day = (datetime.strptime(original_day, "%a") - timedelta(days=1)).strftime("%a").upper()

                    await ScheduleTime.create(
                        schedule=schedule,
                        day=entry.day,
                        from_time=start_time_local.time(),
                        to_time=end_time_local.time()
                    )
                

                except (ValueError, pytz.UnknownTimeZoneError) as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Error processing day {original_day}: {str(e)}"
                    )

            return {"success": True, "detail": "Schedule created successfully"}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while saving the schedule: {str(e)}"
            )









    time_zone = TIMEZONE_ALIASES.get(data.timeZone, data.timeZone)
    try:
        tz = pytz.timezone(time_zone or "UTC")
    except pytz.UnknownTimeZoneError:
        return {"success": False, "detail": f"Invalid timezone: {data.timeZone}"}

    today = datetime.now(tz)

    valid_schedule = [
        schedule_entry for schedule_entry in data.schedule
        if schedule_entry.start and schedule_entry.end
    ]

    if not valid_schedule:
        return {"success": False, "detail": "No valid schedule entries provided"}

    for schedule_entry in valid_schedule:
        day_of_week = schedule_entry.day
        start_time = schedule_entry.start
        end_time = schedule_entry.end

        try:
            start_hour, start_minute = map(int, start_time.split(":"))
            end_hour, end_minute = map(int, end_time.split(":"))
        except ValueError:
            return {"success": False, "detail": f"Invalid time format for day {day_of_week}"}

        if start_hour > end_hour or (start_hour == end_hour and start_minute >= end_minute):
            return {"success": False, "detail": f"Start time must be before end time for day {day_of_week}"}

        current_day = today.weekday()
        target_day = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].index(day_of_week)
        days_until_target = (target_day - current_day + 7) % 7

        start_datetime = today + timedelta(days=days_until_target)
        start_datetime = start_datetime.replace(hour=start_hour, minute=start_minute, second=0)

        if start_datetime < today:
            start_datetime += timedelta(days=7)

        total_minutes = (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
        max_calls = total_minutes // 3

        call_time = start_datetime
        for idx, lead in enumerate(all_leads):
            if idx >= max_calls:
                break

            job = scheduler.add_job(
                trigger_scheduled_call,
                'date',
                run_date=call_time,
                args=[data.vapi_assistant_id, lead.id, user, new_call.id],
            )
            print(f"Scheduled job {job.id} for lead {lead.id} at {call_time}")
            call_time += timedelta(minutes=3)

    await Logs.create(
        user=user,
        message=f"Scheduled a call '{data.title}",
        short_message="add_schedule_call"
    )

    return {"success": True, "detail": "Call(s) scheduled successfully", "call_id": new_call.id}




# @router.get('/get_scheduled_calls')
# async def get_calls(user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
#     try:
#         calls = await ScheduleCall.filter(user=user).order_by("id")
#         results = []
#         for call in calls:
#             call_data = call.__dict__  
           
#             if isinstance(call_data['date'], list):
#                 call_data['date'] = [
#                     d.isoformat() if isinstance(d, datetime) else d
#                     for d in call_data['date']
#                 ]
#             results.append(call_data)
#         return results
#     except Exception as e:
#         return [{"success": False, "detail": str(e)}]
    
@schedule_router.get('/get_schedule_calls')
async def get_user_schedules( user: Annotated[User, Depends(get_current_user)]):
    user_schedules = await Schedule.filter(user__company=user.company_id).prefetch_related('schedule_times').all()
    
    schedule_details = [
        {
            "id": schedule.id,
            "title": schedule.title,
            "timeZone": schedule.timezone,
            # "schedule_times": [
            #     {
            #         "id": schedule_time.id,
            #         "from_time": str(schedule_time.from_time),
            #         "to_time": str(schedule_time.to_time),
            #         "day": schedule_time.day
            #     }
            #     for schedule_time in schedule.schedule_times
            # ]
        }
        for schedule in user_schedules
    ]

    return schedule_details

 
    
# @router.get('/get_schedule_calls')
# async def get_schedule_calls(user: User = Depends(get_current_user)) -> Dict[str, Any]:
#     try:
#         calls = await Schedule.filter(user=user).order_by("id")

#         schedules = {}
#         for call in calls:
#             key = (call.title,  call.timeZone, call.status)
#             if key not in schedules:
#                 schedules[key] = []
#             schedules[key].append({
#                 "day": call.day,
#                 "start": call.from_time.isoformat() if call.from_time else "",
#                 "end": call.to_time.isoformat() if call.to_time else "",
#             })

#         result = [
#             {
#                 "title": title,
#                 "timeZone": timeZone,
#                 "status": status,
#                 "schedule": schedule_list
#             }
#             for (title, timeZone, status), schedule_list in schedules.items()
#         ]

#         return {"success": True, "data": result}

#     except Exception as e:
#         return {"success": False, "detail": str(e)}
 
    
# @router.delete('/delete_scheduled_call/{id}')
# async def delete_calls(id:int, user: Annotated[User, Depends(get_current_user)]):
#     try:
#          call = await Schedule.get_or_none(id= id)
#          await call.delete()
#          await Logs.create(
#                 user = user,
#                 message = f"deleted a scheduled call {call.title}",
#                 short_message = "delete_schedule_call"
#             )
#          return { "success": True, "detail": "File deleted successfully." }

        

#     except Exception as e:
#         return {
#             "success": False,
#             "detail": str(e)
#         }
@schedule_router.delete('/delete_scheduled_call/{id}')
async def delete_calls(id: int, user: Annotated[User, Depends(get_active_user)]):
    try:
        call = await Schedule.get_or_none(id=id, user_id=user.id).prefetch_related("schedule_times")
        
        if not call:
            raise HTTPException(status_code=404, detail="Scheduled call not found")
        
    
        
        await call.schedule_times.all().delete()
        
        await call.delete()

        return {"success": True, "detail": "Scheduled call deleted successfully."}

    except Exception as e:
        return {
            "success": False,
            "detail": f"An error occurred: {str(e)}"
        }   
# @router.get('/get_scheduled_call/{id}')
# async def get_call(id: int, user: Annotated[User, Depends(get_current_user)]):
#     try:
#         return await ScheduleCall.get_or_none(id=id)

#     except Exception as e:
#         return {
#             "success": False,
#             "detail": str(e)
#         }
@schedule_router.get('/get_scheduled_call/{id}')
async def get_scheduled_call(id: int, user: Annotated[User, Depends(get_active_user)]):
    try:
        scheduled_call = await Schedule.get_or_none(id=id, user_id=user.id).prefetch_related("schedule_times")

        if not scheduled_call:
            raise HTTPException(status_code=404, detail="Scheduled call not found")

        response_data = {
            "id": scheduled_call.id,
            "title": scheduled_call.title,
            "timeZone": scheduled_call.timezone,
            "vapi_assistant_id": scheduled_call.user_id,
            "schedule": [
                {
                   "day": time["day"], 
                    "start": time["start"] if isinstance(time["start"], str) else time["start"].strftime("%H:%M"),
                    "end": time["end"] if isinstance(time["end"], str) else time["end"].strftime("%H:%M"),
                }
                for time in scheduled_call.complete_schedule
            ],
        }

        return response_data

    except Exception as e:
        return {
            "success": False,
            "detail": str(e)
        }
@schedule_router.get('/get_scheduled_call')
async def get_call( user: Annotated[User, Depends(get_active_user)]):
    try:
        scheduled_call = await Schedule.filter(user_id=user.id).prefetch_related("schedule_times").first()

        if not scheduled_call:
            raise HTTPException(status_code=404, detail="Scheduled call not found")

        response_data = {
            "id": scheduled_call.id,
            "title": scheduled_call.title,
            "timeZone": scheduled_call.timezone,
            "vapi_assistant_id": scheduled_call.user_id,
            "schedule": [
                {
                   "day": time["day"], 
                    "start": time["start"] if isinstance(time["start"], str) else time["start"].strftime("%H:%M"),
                    "end": time["end"] if isinstance(time["end"], str) else time["end"].strftime("%H:%M"),
                }
                for time in scheduled_call.complete_schedule
            ],
        }

        return response_data

    except Exception as e:
        return {
            "success": False,
            "detail": str(e)
        }

# @router.put('/update_scheduled_call/{id}')
# async def update_call(id:int ,callData : Schedule_Call , user: Annotated[User , Depends(get_current_user)]):
#     try:
#         call = await ScheduleCall.get_or_none(id=id)
#         if not call:
#             raise HTTPException (statuscode = '400' , detail = 'Call not found')
        
#         call.title= callData.title
#         call.file_id = callData.file_id
#         call.vapi_assistant_id = callData.vapi_assistant_id
#         call.timeZone= callData.timeZone
#         call.leads =callData.leads
#         call.date= callData.date
#         call.successEvaluationPrompt= callData.successEvaluationPrompt

#         await call.save()
#         await Logs.create(
#                 user = user,
#                 message = f"updated a scheduled call {call.title}",
#                 short_message = "update_scheduled_call"
#             )
#         return {
#             "success" : True,
#             "detail" : "Updated Successfully"
#         }  
#     except Exception as e:
#         return {
#             "success" :False,
#             "detail":str(e)
#         }


@schedule_router.put('/update_scheduled_call/{id}')
async def update_call(
    id: int,
    callData: Schedule_Call,
    user: Annotated[User, Depends(get_active_user)],
):
    
    if not callData.schedule:
        raise HTTPException(status_code=400, detail="Schedule data is required.")

    # if callData.timeZone not in pytz.all_timezones and callData.timeZone not in TIMEZONE_ALIASES:
    #     raise HTTPException(status_code=400, detail="Invalid timezone provided.")
    user_timezone = TIMEZONE_ALIASES.get(callData.timeZone, callData.timeZone)

    valid_schedule = [
        entry for entry in callData.schedule if entry.start and entry.end
    ]
    complete_valid_schedule = [
    {
        "day": entry.day,
        "start": entry.start,
        "end": entry.end,
    }
    for entry in callData.schedule if entry.start and entry.end
]

    if not valid_schedule:
        raise HTTPException(
            status_code=400,
            detail="Invalid schedule. At least one valid entry with start and end times is required."
        )

    try:
        schedule = await Schedule.get_or_none(id=id, user=user)
        if not schedule:
            raise HTTPException(status_code=404, detail="Scheduled call not found.")

        schedule.title = callData.title
        schedule.timezone = callData.timeZone
        schedule.complete_schedule = json.dumps(complete_valid_schedule)
        await schedule.save()

        existing_times = await ScheduleTime.filter(schedule=schedule).all()
        existing_times_map = {f"{time.day}:{time.from_time}-{time.to_time}": time for time in existing_times}

        new_times_map = {}
        for entry in valid_schedule:
            original_day = entry.day
            start_time_str = entry.start
            end_time_str = entry.end

            try:
                user_tz = pytz.timezone(user_timezone)
                start_time_local = datetime.strptime(start_time_str, "%H:%M").replace(tzinfo=user_tz)
                end_time_local = datetime.strptime(end_time_str, "%H:%M").replace(tzinfo=user_tz)

                # start_time_utc = start_time_local.astimezone(pytz.utc)
                # end_time_utc = end_time_local.astimezone(pytz.utc)

                adjusted_day = original_day
                # if start_time_utc.date() > start_time_local.date():
                #     adjusted_day = (datetime.strptime(original_day, "%a") + timedelta(days=1)).strftime("%a").upper()
                # elif start_time_utc.date() < start_time_local.date():
                #     adjusted_day = (datetime.strptime(original_day, "%a") - timedelta(days=1)).strftime("%a").upper()

                key = f"{adjusted_day}:{start_time_local.time()}-{end_time_local.time()}"
                new_times_map[key] = {
                    "day": adjusted_day,
                    "from_time": start_time_local.time(),
                    "to_time": end_time_local.time(),
                }

            except (ValueError, pytz.UnknownTimeZoneError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error processing day {original_day}: {str(e)}"
                )

        to_delete = set(existing_times_map.keys()) - set(new_times_map.keys())
        to_add = set(new_times_map.keys()) - set(existing_times_map.keys())

        for key in to_delete:
            await existing_times_map[key].delete()

        for key in to_add:
            await ScheduleTime.create(
                schedule=schedule,
                day=new_times_map[key]["day"],
                from_time=new_times_map[key]["from_time"],
                to_time=new_times_map[key]["to_time"]
            )


        return {"success": True, "detail": "Schedule updated successfully."}

    except Exception as e:
        return {"success": False, "detail": str(e)}
    
@schedule_router.get("/scheduled-call/{call_id}/statuses")
async def get_call_statuses(call_id: int,  user: User = Depends(get_current_user) 
):
    call = await ScheduleCall.get_or_none(id=call_id, user=user)
    if not call:
        raise HTTPException(status_code=404, detail="Scheduled call not found.")
    
    lead_statuses = await LeadStatus.filter(schedule_call=call).values("lead_id", "status", "ended_reason" , "customer_name")
    return lead_statuses


@schedule_router.get("/scheduled_call/{schedule_call_id}")
async def get_call_details(schedule_call_id: int, user: User = Depends(get_current_user)):
    print("schedule_call_id", schedule_call_id)
    try:
        schedule_call = await ScheduleCall.get_or_none(id=schedule_call_id)
        if not schedule_call or not schedule_call.call_id or not schedule_call.leads:
            return {"call_details": []} 

        call_details_list = []

        if not isinstance(schedule_call.leads, list) or not isinstance(schedule_call.call_id, list):
            raise HTTPException(status_code=500, detail="Internal server error: leads or call_id is not a list.")

        for lead_id, call_id in zip(schedule_call.leads, schedule_call.call_id):
            call_detail_url = f"https://api.vapi.ai/call/{call_id}"
            response = requests.get(call_detail_url, headers=get_headers())

            if response.status_code != 200:
                call_details_list.append({
                    "lead_id": lead_id,
                    "call_id": call_id,
                    "error": f"Failed to retrieve call details. Status Code: {response.status_code}, Error: {response.text}"
                })
                continue

            call_data = response.json()
            started_at = call_data.get("startedAt", None)
            ended_at = call_data.get("endedAt", None)

            call_duration = None
            if started_at and ended_at:
                start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                call_duration = (end_time - start_time).total_seconds()

            call_info = {
                "lead_id": lead_id,
                "call_id": call_id,
                "status": call_data.get("status", "Unknown"),
                "ended_reason": call_data.get("endedReason", "Unknown"),
                "successEvaluation": call_data.get("costBreakdown", {}).get("analysisCostBreakdown", {}).get("successEvaluation", "Unknown"),
                "call_duration_seconds": call_duration,
            }

            call_details_list.append(call_info)

        return {"call_details": call_details_list}  

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
      
# @router.get("/get_schedulde_requirements")
# async def get_schedulde_requirements(user: Annotated[User, Depends(get_current_user)]):
#     try:
#         current_user = await User.get_or_none(id=user.id)
#         if not current_user:
#             return {"success": False, "detail": "Oops, user not found"}

#         company = await Company.filter(id=user.company_id).first()
#         if not company:
#             return {"success": False, "detail": "Company not found"}

#         company_users = await User.filter(company_id=company.id).all()
#         user_ids = [u.id for u in company_users]

#         assistant = await Assistant.filter(user_id__in=user_ids, assistant_toggle=True).first()

#         phone_number = False
#         lead = False
#         trial = False
#         trialEnds = False
#         schedule = None

#         if assistant:
#             if assistant.attached_Number:
#                 phone_number = True
#             elif await PeoplesGroupMember.filter(user_id=assistant.user_id).exists():
#                 phone_number = True

#             if assistant.leadsfile and len(assistant.leadsfile) > 0:
#                 lead = True

#         if user.has_active_subscription:
#             trial = False
#         elif user.has_free_trial:
#             trial = True
#         else:
#             trialEnds = True

#         sch = await Schedule.filter(user_id=user.id).first()
#         if sch:
#             schedule = sch

#         return {
#             "success": True,
#             "active": assistant is not None,
#             "phone": phone_number,
#             "lead": lead,
#             "trial": trial,
#             "trialEnds": trialEnds,
#             "schedule": schedule
#         }

#     except Exception as e:
#         print("Error while getting the schedule requirements:", str(e))
#         return {"success": False, "detail": str(e)}
