import asyncio
import os
from typing import Annotated, Optional
from fastapi import APIRouter, Depends,HTTPException
import httpx
from helpers.email import send_dnc_email
from helpers.jwt_token import get_admin, get_current_user
# from helpers.send_email import send_dnc_email
from helpers.vapi_helper import generate_token, get_headers
from models.call_log import CallLog
# from models.timeLimit import TimeLimit
from models.defaultSettings import DefaultSettings
from models.dnc import Dnc
from models.dnc import Dnc
from models.lead import Lead
from models.purchased_number import PurchasedNumber
from models.spent import Spent
from models.user import User
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from tortoise.expressions import Q
from models.super_admin_setting import SuperAdminSetting
import asyncio
from datetime import datetime
from typing import Optional
import httpx
import requests
import os

calllogs_router = APIRouter()
token = generate_token()

   
@calllogs_router.get("/all_call_logs")
async def get_logs(user: Annotated[User, Depends(get_admin)]):
    logs = await CallLog.all().select_related("user")

    return [
        {
            "plateform_user_name": log.user.name if log.user else None,
            "plateform_user_email": log.user.email if log.user else None,
            "call_id": log.call_id,
            "call_started_at": log.call_started_at,
            "customer_number": log.customer_number,
            "cost": log.cost,
            "call_ended_at": log.call_ended_at,
            "status": log.status,
        }
        for log in logs
    ]

    
@calllogs_router.get("/user/call-logs") 
async def get_user_call_logs(user: Annotated[User, Depends(get_current_user)]):
    try:
        call_logs = await CallLog.filter(user=user).prefetch_related("user").all()
        
        if not call_logs:
            return []

        return [{"id": log.id,
                 "call_id": log.call_id,
                 "call_started_at": log.call_started_at.isoformat() if log.call_started_at else None,
                 "call_ended_at": log.call_ended_at.isoformat() if log.call_ended_at else None,
                 "cost": str(log.cost) if log.cost else None,
                 "customer_number": log.customer_number,
                 "customer_name": log.customer_name,
                 "call_ended_reason": log.call_ended_reason,
                 "lead_id":log.lead_id
                } for log in call_logs]

    except Exception as e:
        print("An error occurred while retrieving call logs:")
        print(str(e))
        raise HTTPException(status_code=400, detail=f"{str(e)}")
    
@calllogs_router.get("/user/call-logs-detail")
async def get_user_call_logs(user: Annotated[User, Depends(get_current_user)]):
    try:
        # Fetch call logs
        call_logs = await CallLog.filter(user=user).prefetch_related("user").all().order_by("-id")
        
        if not call_logs:
            return []

        # Convert to list of dicts, excluding certain fields
        result = []
        for log in call_logs:
            log_dict = log.__dict__.copy()
            
            # Remove call log sensitive fields
            log_dict.pop("cost", None)
            log_dict.pop("vapi_id", None)

            # Remove password from nested user
            if hasattr(log, "user") and log.user:
                user_dict = log.user.__dict__.copy()
                user_dict.pop("password", None)
                log_dict["user"] = user_dict

            result.append(log_dict)
        
        return result

    except Exception as e:
        print("An error occurred while retrieving call logs:")
        print(str(e))
        raise HTTPException(status_code=400, detail=f"{str(e)}")


@calllogs_router.get("/specific-number-call-logs/{phoneNumber}")
async def call_details(phoneNumber: str, user:Annotated[User, Depends(get_current_user)]):
    try:
        print("phoneNumber",phoneNumber)
        call_details = await CallLog.filter(user=user, customer_number = phoneNumber).all()
        if not call_details:
           return []
        return call_details
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{str(e)}")

@calllogs_router.get("/user/call-cost") 
async def get_user_call_logs(user: Annotated[User, Depends(get_current_user)]):
    try:
        call_logs = await CallLog.filter(user=user).prefetch_related("user").all()
        
        if not call_logs:
            return []
        
        return call_logs

    except Exception as e:
        print("An error occurred while retrieving call logs:")
        print(str(e))
        raise HTTPException(status_code=400, detail=f"An error occurred: {str(e)}")
    

@calllogs_router.get("/call/{call_id}")
async def get_call(call_id: str,user: Annotated[User, Depends(get_current_user)]):
    print("567898yui9")
    try:
        call_detail_url = f"https://api.vapi.ai/call/{call_id}" 
        response = requests.get(call_detail_url, headers=get_headers())
       
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to retrieve call details")

        call_data = response.json()
        
        started_at = call_data.get("startedAt", None)
        ended_at = call_data.get("endedAt", None)
        print("call started at ",started_at)
        print("call ended at ",ended_at)



        call_duration = None
        if started_at and ended_at:
            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))

            call_duration = (end_time - start_time).total_seconds()
        important_info = {
            "recording_url": call_data.get("artifact", {}).get("recordingUrl", "N/A"),
            "transcript": call_data.get("artifact", {}).get("transcript", "No transcript available"),
            "ended_reason": call_data.get("endedReason", "Unknown"),
            "status": call_data.get("status", "Unknown"),
            "call_ended_at":call_data.get("endedAt", None),
            "call_started_at":call_data.get("startedAt", None),
            "created_at": call_data.get("createdAt", "Unknown"),
            "updated_at": call_data.get("updatedAt", "Unknown"),
            "call_duration": call_duration,  
      
            "variableValues": { 
                "name": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("name", "Unknown"),
                "email": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("email", "Unknown"),
                "mobile_no": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("mobile_no", "Unknown"),
                "add_date": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("add_date", "Unknown"),
                "custom_field_01": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("custom_field_01", "Unknown"),
                "custom_field_02": call_data.get("assistantOverrides", {}).get("variableValues", {}).get("custom_field_02", "Unknown"),
            },
            # "successEvalution": success_evalution
        }
        call = await CallLog.get_or_none(call_id = call_id)
        # # time_left = await TimeLimit.filter(user=user).first()
        if call:
             call.call_ended_reason = call_data.get("endedReason", "Unknown")
             call.cost = call_data.get("cost", 0)
             call.status = call_data.get("status", "Unknown")
             call.call_duration = call_duration
             await call.save()
        else:
            await CallLog.create(
             call_id=call_id,
             call_ended_reason=call_data.get("endedReason", "Unknown"),
             cost=call_data.get("cost", 0),
             status=call_data.get("status", "Unknown"),
         )
        
        # time_left.seconds = time_left.seconds - call_duration
        # await time_left.save()
                    
        return important_info

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

 
@calllogs_router.delete("/call_log/{id}")
async def delete_calls(id:str):
    try:
        url = f"https://api.vapi.ai/call/{id}"
        headers = {
            "Authorization" :f"Bearer {token}"
        }
        response = requests.request("DELETE", url, headers=headers)
        if response.status_code not in [200, 204]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"VAPI phone number detachment failed with status {response.status_code}: {response.text}"
                )
        await CallLog.filter(call_id=id).delete()
        return{"success":True, "detail" : "Call log delted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Error Fetching Call logs: {str(e)}")
    

@calllogs_router.get("/update_calls")
async def update_call_logs_for_missing_details():
    try:        
        calls_to_update = await CallLog.filter(
            Q(call_ended_reason__isnull=True) | Q(call_duration__isnull=True)
        ).all()
        
        if not calls_to_update:
            print("No calls need to be updated.")
            return {"message": "No calls need to be updated."}
        
        updated_count = 0
        
        for call in calls_to_update:
            call_id = call.call_id
            print(f"Fetching details for call: {call_id}")
            
            call_detail_url = f"https://api.vapi.ai/call/{call_id}"
            async with httpx.AsyncClient() as client:
                response = await client.get(call_detail_url, headers=get_headers())
            
            if response.status_code != 200:
                print(f"Failed to retrieve details for call {call_id}, status code {response.status_code}")
                continue  
                
            call_data = response.json()
            started_at = call_data.get("startedAt", None)
            ended_at = call_data.get("endedAt", None)
            call_ended_reason = call_data.get("endedReason", "Unknown")
            cost = call_data.get("cost", 0)
            status = call_data.get("status", "Unknown")
            transcript = call_data.get("artifact", {}).get("transcript", "No transcript available")
            
            call_duration = None
            if started_at and ended_at:
                try:
                    start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    end_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                    call_duration = (end_time - start_time).total_seconds()
                except ValueError as date_error:
                    print(f"Error parsing dates for call {call_id}: {date_error}")
                    call_duration = 0
            
            call.call_ended_reason = call_ended_reason
            call.cost = cost
            call.status = status
            call.call_duration = call_duration if call_duration else 0
            
            if ended_at:
                try:
                    call.call_ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                except ValueError as date_error:
                    print(f"Error parsing end date for call {call_id}: {date_error}")
                    call.call_ended_at = None
            
            await call.save()
            updated_count += 1
            print(f"Successfully updated call {call_id}")
            
        return {"message": f"Successfully updated {updated_count} calls"}
        
    except Exception as e:
        print(f"Error in update_call_logs_for_missing_details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def get_call_details(call_id: str, delay: int ,user_id :int, lead_id : Optional[int] = None ):
    print("background task-----------------------")
    try:
        print(f"Task will run after {delay}")
        await asyncio.sleep(delay)
        call_detail_url = f"https://api.vapi.ai/call/{call_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(call_detail_url, headers=get_headers())
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to retrieve call details")

        call_data = response.json()
        started_at = call_data.get("startedAt", None)
        ended_at = call_data.get("endedAt", None)        
        transcript= call_data.get("artifact", {}).get("transcript", "No transcript available")
        
        user = await User.filter(id=user_id).first()
        
        # is_transferred = False
        dnc = False
        
        # try:
        #     transfer_result = await analyze_call_transfer(transcript)
        #     is_transferred = transfer_result.get("isTransferred", False)
        #     print(f"is talk with human : {is_transferred}")
        # except Exception as e:
        #     print(f"Error in analyze_call_transfer but continue to save other call logs: {str(e)}")
        #     is_transferred = False
        
        try:
            dnc_prompts = await Dnc.all()
            prmpt_list = [dnc.prompt for dnc in dnc_prompts]
            dnc_result = await analyze_dnc(transcript, prmpt_list)
            dnc = dnc_result.get("dnc_detected", False)
        except Exception as e:
            print(f"Error in analyze_dnc but continue to save other call logs: {str(e)}")
            dnc = False
        

        lead = await Lead.filter(id=lead_id).first()
        if lead:
            if dnc:
               send_dnc_email(user.email, lead.email, lead.first_name, lead.last_name)
               lead.dnc = dnc
               await lead.save()

        
        is_transferred = False
        try:
            transfer_result = await analyze_call_transfer(transcript)
            is_transferred = transfer_result.get("isTransferred", False)
        except Exception as e:
            print(f"Error in analyze_call_transfer but continue to save other call logs: {str(e)}")
            is_transferred = False

        call_duration = None
        if started_at and ended_at:
            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            call_duration = (end_time - start_time).total_seconds()

        if is_transferred:
            transfer_rate = 0
            defaultSettings = await DefaultSettings.first()
            transfer_rate = defaultSettings.transfer_rate
            
            call_cost = (call_duration / 60) * transfer_rate if call_duration > 0 else 0
            if call_cost > 0:
                await Spent.create(
                    user=user,
                    spent_money=call_cost,  
                    description="Transferred a call"
                )
        call = await CallLog.get_or_none(call_id=call_id)
        # time_left= await TimeLimit.get_or_none(user_id=user_id)
        print("updaing call logs")
        if call:
            call.is_transferred = is_transferred
            call.call_ended_reason = call_data.get("endedReason", "Unknown")
            call.cost = call_data.get("cost", 0)
            call.status = call_data.get("status", "Unknown")
            call.call_duration = call_duration if call_duration else 0
            call.criteria_satisfied = is_transferred
            
            if isinstance(ended_at, str):
                call.call_ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            else:
                call.call_ended_at = ended_at
            # if time_left and call_duration:
            #     time_left.seconds = time_left.seconds - call_duration
            #     await time_left.save()
            await call.save()
        else:
            await CallLog.create(
                # is_transferred = is_transferred,
                call_id=call_id,
                call_ended_reason=call_data.get("endedReason", "Unknown"),
                cost=call_data.get("cost", 0),
                status=call_data.get("status", "Unknown"),
                call_ended_at=datetime.fromisoformat(ended_at.replace("Z", "+00:00")) if isinstance(ended_at, str) else ended_at,
                call_duration=call_duration,
                # criteria_satisfied = is_transferred

            )
            print("Call log save")
            # if time_left and call_duration:
            #     time_left.seconds = time_left.seconds - call_duration
            #     await time_left.save()

    except Exception as e:
        print(f"Error in get_call_details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



    
#this will use for scheduler call details only as background task is only available in the context of FasApi and our scheduler is not in that so it is not support the background taks we use it through the asyncio and handle the call logs and update them 
async def get_call_detail(call_id: str, delay: int, user_id: int, lead_id: Optional[int] = None):
    """
    Async function to get call details after a delay
    This runs as an independent asyncio task
    """
    print(f"Starting background task for call_id: {call_id}, delay: {delay}s")
    
    try:
        # Wait for the specified delay
        await asyncio.sleep(delay)
        print(f"Processing call details for call_id: {call_id}")
        
        # Get call details from VAPI
        call_detail_url = f"https://api.vapi.ai/call/{call_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(call_detail_url, headers=get_headers())
        
        if response.status_code != 200:
            print(f"Failed to retrieve call details: {response.status_code} - {response.text}")
            return
        
        call_data = response.json()
        started_at = call_data.get("startedAt")
        ended_at = call_data.get("endedAt")
        transcript = call_data.get("artifact", {}).get("transcript", "No transcript available")
        
        print(f"Call data retrieved - Started: {started_at}, Ended: {ended_at}")
        
        # Get user and main admin
        user = await User.filter(id=user_id).first()
        if not user:
            print(f"User with id {user_id} not found")
            return
        
    
 
        
        transfer_result = {"isTransferred": False}
        # try:
        #     if transcript and transcript != "No transcript available":
        #         transfer_result = await analyze_call_transfer(transcript)
        #         print(f"Transfer analysis completed: {transfer_result}")
        # except Exception as e:
        #     print(f"Transfer analysis failed: {str(e)}")
            # Continue with default value
        
        # Analyze DNC with error handling
        dnc = False
        try:
            dnc_prompts = await Dnc.all()
            if dnc_prompts:
                prmpt_list = [dnc.prompt for dnc in dnc_prompts]
                if transcript and transcript != "No transcript available":
                    dnc = await analyze_dnc(transcript, prmpt_list)
                    print(f"DNC analysis completed: {dnc}")
        except Exception as e:
            print(f"DNC analysis failed: {str(e)}")
            # Continue with default value
        
        # Update lead with DNC status
        if lead_id and dnc:
            try:
                lead = await Lead.filter(id=lead_id).first()
                if lead:
                    send_dnc_email(user.email, lead.email, lead.first_name, lead.last_name)
                    lead.dnc = dnc
                    await lead.save()
                    print(f"Lead {lead_id} updated with DNC status")
            except Exception as e:
                print(f"Failed to update lead DNC status: {str(e)}")
        
        # Handle transfer charges
        # is_transferred = transfer_result.get("isTransferred", False)
        # if is_transferred:
        #     try:
        #         transfer_rate = 0
        #         user_setting = await VVadminSetting.filter(user=main_admin).first()
                
        #         if user_setting and user_setting.transfer_rate:
        #             transfer_rate = user_setting.transfer_rate
        #         else:
        #             default_settings = await DefaultSettings.first()
        #             if default_settings:
        #                 transfer_rate = default_settings.transfer_rate
                
        #         if transfer_rate > 0:
        #             await Spent.create(
        #                 user=main_admin,
        #                 spent_money=transfer_rate,
        #                 description="Transferred a call"
        #             )
        #             print(f"Transfer charge applied: ${transfer_rate}")
        #     except Exception as e:
        #         print(f"Failed to apply transfer charges: {str(e)}")
        
        # Calculate call duration
        call_duration = 0
        if started_at and ended_at:
            try:
                start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                call_duration = (end_time - start_time).total_seconds()
                print(f"Call duration calculated: {call_duration} seconds")
            except Exception as e:
                print(f"Failed to calculate call duration: {str(e)}")
        is_transferred = True
        if is_transferred:
            try:
                transfer_rate = 0
                user_setting = await SuperAdminSetting.filter(user=user).first()
                
                if user_setting and user_setting.transfer_rate:
                    transfer_rate = user_setting.transfer_rate
                else:
                    default_settings = await DefaultSettings.first()
                    if default_settings:
                        transfer_rate = default_settings.transfer_rate
                call_cost = (call_duration / 60) * transfer_rate if call_duration > 0 else 0
                if call_cost > 0:
                    await Spent.create(
                        user=user,
                        spent_money=transfer_rate,
                        description="Transferred a call"
                    )
                    print(f"Transfer charge applied: ${transfer_rate}")
            except Exception as e:
                print(f"Failed to apply transfer charges: {str(e)}")
        # Update call log and time limit
        try:
            call = await CallLog.get_or_none(call_id=call_id)
            
            if call:
                # Update existing call log
                call.is_transferred = is_transferred
                call.call_ended_reason = call_data.get("endedReason", "Unknown")
                call.cost = call_data.get("cost", 0)
                call.status = call_data.get("status", "Unknown")
                call.call_duration = call_duration
                call.criteria_satisfied = is_transferred
                
                if ended_at:
                    if isinstance(ended_at, str):
                        call.call_ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                    else:
                        call.call_ended_at = ended_at
                
                await call.save()
                print(f"Call log updated for call_id: {call_id}")
            else:
                # Create new call log
                await CallLog.create(
                    is_transferred=is_transferred,
                    call_id=call_id,
                    call_ended_reason=call_data.get("endedReason", "Unknown"),
                    cost=call_data.get("cost", 0),
                    status=call_data.get("status", "Unknown"),
                    call_ended_at=datetime.fromisoformat(ended_at.replace("Z", "+00:00")) if isinstance(ended_at, str) and ended_at else None,
                    call_duration=call_duration,
                    criteria_satisfied=is_transferred
                )
                print(f"New call log created for call_id: {call_id}")
            
            # # Update time limit
            # if call_duration > 0:
            #     time_left = await TimeLimit.get_or_none(user_id=user_id)
            #     if time_left:
            #         time_left.seconds = max(0, time_left.seconds - call_duration)
            #         await time_left.save()
            #         print(f"Time limit updated: {call_duration}s deducted")
        
        except Exception as e:
            print(f"Failed to update call log: {str(e)}")
        
        print(f"Background task completed successfully for call_id: {call_id}")
    
    except asyncio.CancelledError:
        print(f"Background task cancelled for call_id: {call_id}")
        raise
    except Exception as e:
        print(f"Unexpected error in background task for call_id {call_id}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")


def create_background_task(call_id: str, delay: int, user_id: int, lead_id: Optional[int] = None):
    """
    Creates an asyncio task with proper error handling
    Returns the task so it can be tracked if needed
    """
    async def task_wrapper():
        try:
            await get_call_detail(call_id, delay, user_id, lead_id)
        except Exception as e:
            print(f"Background task failed for call_id {call_id}: {str(e)}")
    
    task = asyncio.create_task(task_wrapper())
    print(f"Background task created for call_id: {call_id}")
    return task


async def analyze_call_transfer(transcript: str) -> dict:
    prompt = """
    Did the conversation start with the AI agent calling the user, and did the user pick up the call? 
    Based on the provided transcript, please determine if the conversation involves the AI agent speaking directly with the human user 
    or if an automated system (bot) responded on the user's side.

    If the conversation is between the AI agent and a human (user), just respond with: 
    isTransferred: True

    If a bot or automated system responded on the user's side instead of the user speaking directly, just respond with:
    isTransferred: False

    Transcript:
    {transcript}
    """
    prompt = ChatPromptTemplate.from_template(prompt)
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    result = await chain.ainvoke({
        "transcript": transcript
    })
    
    is_transferred = "True" if "True" in result else "False"
    
    return {"isTransferred": is_transferred == "True"}

async def analyze_dnc(transcript: str, dnc_prompts: list) -> dict:
    dnc_prompts_str = [str(dnc) for dnc in dnc_prompts] 
    prompt = f"""
    You are analyzing a call transcript to check if the user expressed any intention to be added to the "Do Not Call" (DNC) list.
    Below is a list of DNC-related prompts:
    {', '.join(dnc_prompts_str)}

    Analyze the following transcript and determine if the user's intent matches any of the above DNC prompts or if their intent is related to the DNC list.

    Provide your response in True or False only.

    Transcript:
    {transcript}
    """

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    output_parser = StrOutputParser()

    prompt_template = ChatPromptTemplate.from_template(prompt)
    chain = prompt_template | model | output_parser

    result = await chain.ainvoke({"transcript": transcript})

    if result.strip().lower() == "true":
        return {"dnc_detected": True}
    elif result.strip().lower() == "false":
        return {"dnc_detected": False}
    else:
        return {"error": f"Unexpected model response: {result}"}
    
    





async def handle_end_of_call_report(payload):
    """Handle end-of-call-report and save to CallLog"""
    try:

        message = payload.get("message", {})

        call_data = message.get("call", {})

        # Extract call information
        vapi_call_id = call_data.get("id")
        call_type = call_data.get("type", "inbound")
        started_at = call_data.get("startedAt")
        ended_at = call_data.get("endedAt")

        ended_reason = message.get("endedReason")
        call_duration_seconds = message.get("durationSeconds")
        call_started_at = message.get("startedAt")
        call_ended_at = message.get("endedAt")


        cost = message.get("cost", 0.0)

    
        # ✅ Correct number extraction (VERY IMPORTANT)
        customer_number = call_data.get("customer", {}).get("number")
        called_number = message.get("phoneNumber", {}).get("number")

        lead_number = None
        lead_name  = None
        lead_id = None
        if customer_number:
            lead = await Lead.filter(mobile=customer_number).first()
            if lead:
               lead_name = f"{lead.first_name}  {lead.last_name}"
               lead_number = lead.mobile 
               lead_id = lead.id
               

        user = None
        if called_number:
            try:
                purchased_num = await PurchasedNumber.filter(phone_number=called_number).first()

                if purchased_num:
                    user = await User.filter(id=purchased_num.user_id).first()
                else:
                    print("NO PURCHASED NUMBER FOUND")

            except Exception as e:
                return {"error": f"Unable to find user: {e}"}

        # Analysis data
        analysis = message.get("analysis", {})
        structured_data = analysis.get("structuredData", {})

        customer_name = None
        if isinstance(structured_data, dict):
            customer_name = (
                structured_data.get("customerName")
                or structured_data.get("customer_name")
                or structured_data.get("name")
            )


        # Transfer detection
        is_transferred = False
            
        try:
            transfer_result = await analyze_call_transfer(transcript)
            is_transferred = transfer_result.get("isTransferred", False)
        except Exception as e:
            print(f"Error in analyze_call_transfer but continue to save other call logs: {str(e)}")
            is_transferred = False
        # Success evaluation
        criteria_satisfied = False
        # success_evaluation = analysis.get("successEvaluation", {})

        # if success_evaluation:
        #     score = success_evaluation.get("score", 0)
        #     criteria_satisfied = score >= 7

        # print("Criteria Satisfied:", criteria_satisfied)

        # Create CallLog entry
        call_log_data = {
            "vapi_id": vapi_call_id,
            "call_id":vapi_call_id,
            "call_type": call_type,
            "user": user,
            "customer_name": lead_name if lead_name else customer_name,
            "lead_id" : lead_id,
            "call_started_at": call_started_at,
            "call_ended_at": call_ended_at,
            "call_ended_reason": ended_reason,
            "call_duration": call_duration_seconds,
            "customer_number": customer_number,
            "cost": cost,
            "is_transferred": is_transferred,
            "status": "completed",
            "criteria_satisfied": criteria_satisfied
        }

        call_log_data = {k: v for k, v in call_log_data.items() if v is not None}


        await CallLog.create(**call_log_data)
        user_settings = await SuperAdminSetting.filter(user=user).first()
        if user_settings:
            transfer_rate = user_settings.transfer_rate
        else:
            default_settings = await DefaultSettings.first()
            if default_settings:
                transfer_rate = default_settings.transfer_rate
        cost = (call_duration_seconds / 60) * transfer_rate if call_duration_seconds > 0 else 0
        
        await Spent.create(
            user=user,
            spent_money=cost,
            description="Call Cost"
        )
        print("✅ CALL LOG SAVED SUCCESSFULLY")

    except Exception as e:
        print("❌ ERROR SAVING CALL LOG:", e)
        return {"error": f"Unable to save the call logs: {e}"}
