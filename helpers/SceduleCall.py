from fastapi import HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List
import requests
import os
from controllers.call_controller import create_background_task
from helpers.vapi_helper import get_headers
from models.assistant import Assistant
from models.call_log import CallLog
from models.lead import Lead
from models.user import User
from helpers.criteria_check import can_process_call
from helpers.call_duration import get_total_call_duration
from datetime import datetime
import requests
import os
from datetime import datetime, timedelta
import pytz
from models.super_admin_setting import SuperAdminSetting


class ScheduleCallRequest(BaseModel):
    vapi_assistant_id: str
    lead_ids: List[int]
    scheduled_time: datetime
    successEvaluationPrompt: str


async def check_lead_call_interval(lead_id: int) -> bool:

    current_time = datetime.now(pytz.utc)  
    
    minutes_ago = current_time - timedelta(hours=3)
    
    lead = await Lead.get_or_none(id=lead_id)
    if not lead:
        return False
    
    if not lead.last_called_at:
        return True
    
    if lead.last_called_at < minutes_ago:
        return True
    
    print(f"Lead {lead_id} was called less than 3 hours ago. Skipping...")
    return False

async def assistant_call(vapi_assistant_id: str, lead_id: int, user: User):

    print(f'Starting assistant_call for lead_id: {lead_id}')
    
    try:
        # Block any scheduled calls for inactive users
        if not user.is_active:
            return {"success": False, "detail": "Your account is inactive. Please contact support."}

        # Check if enough time has passed since last call 
        if not await check_lead_call_interval(lead_id):
            return {"success": False, "detail": "Call interval not met (20 minutes required)"}
        
        assistant = await Assistant.get_or_none(vapi_assistant_id=vapi_assistant_id)
        lead = await Lead.get_or_none(id=lead_id)
        
        if lead.call_count is not None and lead.call_count >= 3:
            print(f"Lead {lead.id} has reached the maximum call count. Skipping...")
            return {"success": False, "detail": "Maximum call count reached"}
        
        already_called = await CallLog.filter(lead_id=lead_id).values_list('is_transferred', flat=True)
        if any(already_called):
            print("Lead has already been transferred")
            return {"success": False, "detail": "Lead already transferred"}
        
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        mobile_no = lead.mobile if lead.mobile.startswith('+') else f"+1{lead.mobile}"

        # # older one 
        # if assistant.attached_Number is None:
        #     raise HTTPException(status_code=404, detail="No Number Attached with this Assistant")
        
        # new check if can use shared number or attach number
        # result = await get_user_phone_number(user_id=user.id,state=lead.state if lead.state else None)
        # if result:
        #     print(f"Phone: {result['phone_number']}")
        # else:
        #     print("User not authorized or no numbers available")

        
        # Check phone number availability
        if assistant.attached_Number is None and (not result or result['phone_number'] is None):
            return {"success": False, "detail": "Unable to call! No Number Attached with this Assistant"}
        
        # Assign the phone number to use
        phone_number = result['phone_number'] if result and result['phone_number'] is not None else assistant.attached_Number

        total_call_duration = await get_total_call_duration(user.id)
        print(f"Total call duration for user: {total_call_duration}")

        process = await can_process_call(user.id)
        if not process:
            print("User cannot process call - trial expired and no active subscription")
            return {"success": False, "detail": "User cannot process, trial expired and no active subscription."}
        
        
        setting = await SuperAdminSetting.filter(user_id=user.id).first()
        
        #get max_call limit free trail
        max_call_limit = setting.max_call_limit_free_trial if setting and setting.max_call_limit_free_trial is not None else 2000
        
        print(f"The max call limit for this user is {max_call_limit}")
        if user.has_free_trial and total_call_duration > max_call_limit:
            print("Total call duration exceeds trial limit")
            return {"success": False, "detail": "Total call duration exceeds the limit of 2000 minutes."}
        
        # Get max call duration
        max_call_duration = setting.max_call_duration if setting and setting.max_call_duration is not None else 150
        
        max_call_duration = max_call_duration if max_call_duration > 150 else 150
        
        print(f"Max call duraton set to: {max_call_duration} seconds")
        print(f"Lead other_data: {lead.other_data}")
        # print(f"Lead other_data type: {type(lead.other_data)}")
        
        custom_field_01 = None
        custom_field_02 = None
        
        if lead.other_data:
            if isinstance(lead.other_data, dict):
                custom_field_01 = lead.other_data.get('Custom_0')
                custom_field_02 = lead.other_data.get('Custom_1')
            elif isinstance(lead.other_data, list) and len(lead.other_data) > 0:
                custom_field_01 = lead.other_data[0] if len(lead.other_data) > 0 else None
                custom_field_02 = lead.other_data[1] if len(lead.other_data) > 1 else None
        
        print(f"Custom field 01: {custom_field_01}")
        print(f"Custom field 02: {custom_field_02}")
                
        print(f"max_call_duration is {max_call_duration}")
        # Prepare VAPI call payload
        call_url = "https://api.vapi.ai/call"
        payload = {
            "name": "From AIBC",
            "assistantId": vapi_assistant_id,    
            "customer": {
                "numberE164CheckEnabled": True,
                "extension": None,
                "number": mobile_no,
            },
            "phoneNumber": {
                "fallbackDestination": {
                    "type": "number",
                    "numberE164CheckEnabled": True,
                    "number": mobile_no,
                },
                "twilioAccountSid": os.environ.get('TWILIO_ACCOUNT_SID'),
                "twilioAuthToken": os.environ.get('TWILIO_AUTH_TOKEN'),
                "twilioPhoneNumber": phone_number
            },
            "assistantOverrides": {
                "variableValues": {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "email": lead.email,
                    "add_date": lead.add_date.isoformat(),
                    "custom_field_01": custom_field_01,
                    "custom_field_02": custom_field_02,
                },
                "maxDurationSeconds": max_call_duration
            }
        }
                # Make the VAPI call
        response = requests.post(call_url, json=payload, headers=get_headers())
        print(f"VAPI response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            vapi_response_data = response.json()
            call_id = vapi_response_data.get("id")
            started_at = vapi_response_data.get("createdAt")
            
            if not call_id:
                raise HTTPException(status_code=400, detail="No callId found in the VAPI response.")
            
            # Create call log
            first_name = vapi_response_data.get("assistantOverrides", {}).get("variableValues", {}).get("first_name")
            last_name = vapi_response_data.get("assistantOverrides", {}).get("variableValues", {}).get("last_name")
            customer_name = f"{first_name} {last_name}"
            
            new_call_log = CallLog(
                user=user,
                call_id=call_id,
                call_started_at=started_at,
                customer_name=customer_name,
                customer_number=lead.mobile,
                lead_id=lead_id
            )
            await new_call_log.save()
            
            lead.call_count = (lead.call_count or 0) + 1
            lead.last_called_at = datetime.now()
            await lead.save()
            

            task_delay = max_call_duration + 200  
            create_background_task(
                call_id=call_id,
                delay=task_delay,
                user_id=user.id,
                lead_id=lead_id
            )
            
            print(f"Call initiated successfully. Background task will run in {task_delay} seconds")
            
            return {
                "success": True,
                "detail": "Call initiated successfully",
                "vapi_response": vapi_response_data,
                "background_task_created": True
            }
        else:
            print(f"VAPI call failed: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"VAPI call initiation failed: {response.text}"
            )
    
    except Exception as e:
        print(f"Error in assistant_call: {str(e)}")
        raise HTTPException(status_code=400, detail=f"An error occurred: {str(e)}")







async def trigger_scheduled_call(vapi_assistant_id: str, lead_id: int, user: User, callid: int):
    await assistant_call(vapi_assistant_id, lead_id, user, callid)
