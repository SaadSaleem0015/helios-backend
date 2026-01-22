from datetime import date, datetime, time, timedelta
from typing import Annotated, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
import httpx
from controllers.call_controller import get_call_details, handle_end_of_call_report
from helpers.criteria_check import balance_count, has_payment_method, minimum_balance_for_call
from helpers.jwt_token import get_admin, get_current_user
from models.assistant import Assistant
from models.call_log import CallLog
from models.lead import Lead
from models.super_admin_setting import SuperAdminSetting
from models.defaultSettings import  DefaultSettings
from models.purchased_number import PurchasedNumber
from helpers.vapi_helper import user_add_payload,get_headers,generate_token
from models.user import User
import os
import pytz
import dotenv
import requests
# from helpers.call_duration import get_total_call_duration
from pydantic import BaseModel,EmailStr
import json
import json
import os
import httpx


dotenv.load_dotenv()
assistant_router = APIRouter()
header = get_headers()
token = generate_token()
VAPI_WEBHOOK_URL = "https://ff4f88149eb4.ngrok-free.app/api/webhooks/vapi"

class PhoneCallRequest(BaseModel):
    api_key: str
    first_name: str
    email: EmailStr
    number: str
    agent_id:Optional[str] = None

class AssistantCreate(BaseModel):
    name: str
    provider: str
    first_message: str
    model: str
    systemPrompt: str
    knowledgeBase: Optional[list]
    leadsfile : Optional[List[int]] = []
    temperature: float
    maxTokens: int
    transcribe_provider: str
    transcribe_language: str
    transcribe_model: str
    languages:Optional[List[str]] = []
    forwardingPhoneNumber: Optional[str] = None
    endCallPhrases: Optional[List[str]] = []
    voice_provider: str
    voice: str
    voice_model:str
    attached_Number: Optional[str] =None
    draft: Optional[bool] = False
    assistant_toggle: Optional[bool] = True
    category:Optional[str] = None
    tools: Optional[List] = None

    # success_evalution: Optional[str] =None
    
class AdminAssistantUpdate(BaseModel):
    name: str
    provider: str
    first_message: str
    model: str
    systemPrompt: str
    knowledgeBase: List[str]  
    temperature: float
    maxTokens: int
    transcribe_provider: str
    transcribe_language: str
    transcribe_model: str
    voice_provider: str
    voice: str
    dialKeypadEnabled: Optional[bool] = False
    endCallFunctionEnabled: Optional[bool] = False
    forwardingPhoneNumber: Optional[str] = None
    endCallPhrases: Optional[List[str]] = None
    silenceTimeoutSeconds: Optional[int] = None
    hipaaEnabled: Optional[bool] = None
    audioRecordingEnabled: Optional[bool] = False
    videoRecordingEnabled: Optional[bool] = False
    maxDurationSeconds: Optional[int] = None
    interruptionThreshold: Optional[int] = 0
    responseDelay: Optional[float] = 0
    llmRequestDelay: Optional[float] = 0
    clientMessages: Optional[List[str]] = []
    serverMessages: Optional[List[str]] = []
    endCallMessage: Optional[str] = None
    idleMessages: Optional[List[str]] = []
    idleTimeoutSeconds: Optional[float] = None
    idleMessageMaxSpokenCount: Optional[int] = None
    summaryPrompt: Optional[str] = None
    successEvaluationPrompt: Optional[str] = None
    structuredDataPrompt: Optional[str] = None
    attached_Number: Optional[str] =None
    category:Optional[str] = None
class DataForCall(BaseModel):
  first_name: str
  last_name: str
  email: str
  add_date: str
  mobile_no: str
  custom_field_01: Optional[str] = None
  custom_field_02: Optional[str] = None

class DataForCallDemo(BaseModel):
  first_name: str 
#   last_name: str
  email: Optional[str] = None
#   add_date: str
  mobile_no: str
#   custom_field_01: Optional[str] = None
#   custom_field_02: Optional[str] = None

class AssistantToggle(BaseModel):
    id: int
    assistant_toggle: bool
class AttachNumberRequest(BaseModel):
    phone_number: str
    assistant_id: int



class Languages(BaseModel):
    languages: List[str]
    
from fastapi import APIRouter, Request, HTTPException, Response
from pydantic import BaseModel
import os
from typing import Dict, Any


class VapiAssistantRequest(BaseModel):
    message: Dict[str, Any]
    call: Dict[str, Any]

@assistant_router.post("/webhooks/vapi")
async def vapi_webhook(request: Request):
    """
    Handles Vapi server events, primarily 'assistant-request' for inbound call gating.
    - Checks user balance for the called number.
    - Rejects low-balance calls with a spoken message.
    - Allows by returning the user's assistantId.
    """
    print("Webhook call hwi hai", request)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    message_type = payload.get("message", {}).get("type")
    print("message_type", message_type)
    if message_type == "end-of-call-report":
        await handle_end_of_call_report(payload)
        return Response(status_code=204)
    
    if message_type != "assistant-request":
        # Acknowledge other events (e.g., future call-started, end-of-call-report)
        return Response(status_code=204)  # No content – Vapi expects quick ack
   
    print("payload", payload)
    # Extract key info from call
    call_data = payload.get("call", {})
    called_number = payload["message"]["phoneNumber"]["number"]
    caller_number = payload["message"]["call"]["customer"]["number"]
    print("Caller:", caller_number)
    print("Called:", called_number)
    
    if not called_number:
        # Rare, but reject if no called number
        return {"error": "Invalid call routing. Please contact support."}
    
    # Lookup the purchased number → user
    purchased_num = await PurchasedNumber.filter(phone_number=called_number).first()
    if not purchased_num:
        return {"error": "This number is not active currently."}
    print("purchased_num", purchased_num.phone_number)
    
    
    user = await User.filter(id=purchased_num.user_id).first()
    print("user", user.email)
      # Assuming user relation
    if not user:
        return {"error": "Account not found for this number."}
    print("caller_number  aa hai 1222312 userrrrrrrrrrr----- ",called_number)
    
    # Your balance/threshold check (adapt to your logic)
    # Example: require at least $5 or whatever your min is
    user_balance = await balance_count(user.id)  # Or user.balance if direct field
    if user_balance < 5:
        return {
            "error": "Sorry, your account balance is too low to receive calls right now. "
                     "Please top up your account via the dashboard and try again."
        }
    assistant = await Assistant.filter(vapi_phone_uuid = purchased_num.vapi_phone_uuid).first()

    # Optional: Add more checks (e.g., business hours, user active status, spam caller, etc.)
    # if not await is_business_hours():
    #     return {"error": "We're currently closed. Please call during business hours."}

    # Allowed → Return the saved assistant ID (fastest, uses your pre-created assistant)
    # Store assistantId in PurchasedNumber or User when creating assistant
    assistant_id = assistant.vapi_assistant_id  # Adjust field name if different
    print("assistant_id ----- ",assistant_id)

    if not assistant_id:
        # Fallback: reject or return transient config
        return {"error": "No assistant configured for this number."}

    return {"assistantId": assistant_id}

    # Alternative: Return full transient assistant config (if you want dynamic per-call changes)
    # return {
    #     "assistant": {
    #         "firstMessage": "Hello! Welcome to our service.",
    #         "model": {"provider": "openai", "model": "gpt-4o-mini"},
    #         "voice": {"provider": "elevenlabs", "voiceId": "your-voice-id"},
    #         # Add system prompt, etc.
    #     }
    # } 

@assistant_router.post("/assistants")
async def create_assistant(assistant: AssistantCreate, user: User = Depends(get_current_user)):
    try:
        balance = await balance_count(user.id)
        if balance < 5:
                print("Insufficient balance, skipping...")
                return {"success" : False, "detail": "Insufficient balance."}

        required_fields = [
            'name', 'provider', 'first_message', 'model',
            'systemPrompt', 'temperature',
            'maxTokens', 'transcribe_provider',
            'transcribe_language', 'transcribe_model', 'voice_provider', 'voice',
        ]
        empty_fields = [field for field in required_fields if not getattr(assistant, field, None)]
        if empty_fields:
            raise HTTPException(status_code=400, detail=f"All fields are required. Empty fields: {', '.join(empty_fields)}")

        payload_data =await user_add_payload(assistant,user)
        
        headers = get_headers()  
        url = "https://api.vapi.ai/assistant"  
        
        response = requests.post(url=url, json=payload_data, headers=headers)  

        if response.status_code in [200, 201]:
          
            vapi_response_data = response.json()
            vapi_assistant_id = vapi_response_data.get('id')
            
            existing_assistants = await Assistant.filter(user=user).all().count()
            assistant_toggle = existing_assistants == 0

            new_assistant = await Assistant.create(
                user=user,
                name=assistant.name,
                provider=assistant.provider,
                first_message=assistant.first_message,
                model=assistant.model,
                systemPrompt=assistant.systemPrompt,
                knowledgeBase=assistant.knowledgeBase, 
                leadsfile = assistant.leadsfile,
                temperature=assistant.temperature,
                maxTokens=assistant.maxTokens,
                transcribe_provider=assistant.transcribe_provider,
                transcribe_language=assistant.transcribe_language,
                transcribe_model=assistant.transcribe_model,
                voice_provider=assistant.voice_provider,
                forwardingPhoneNumber=assistant.forwardingPhoneNumber,
                endCallPhrases=assistant.endCallPhrases,
                voice=assistant.voice,
                vapi_assistant_id=vapi_assistant_id,
                attached_Number=assistant.attached_Number,
                draft = assistant.draft,
                assistant_toggle = assistant_toggle,
                category= assistant.category,
                voice_model = assistant.voice_model,
                languages = assistant.languages
                # success_evalution=assistant.success_evalution
            )
          


            
            if assistant.attached_Number:
                new_number_uuid = None
                new_phonenumber = await PurchasedNumber.filter(phone_number = assistant.attached_Number).first()
                new_number_uuid = new_phonenumber.vapi_phone_uuid
                isNumberAttachedWithPreviousAssistant = await Assistant.filter(vapi_phone_uuid = new_number_uuid , user = user).first()

                if isNumberAttachedWithPreviousAssistant:
                       isNumberAttachedWithPreviousAssistant.vapi_phone_uuid = None
                       isNumberAttachedWithPreviousAssistant.attached_Number = None
                       await isNumberAttachedWithPreviousAssistant.save() 
                
                requests.patch(
                f"https://api.vapi.ai/phone-number/{new_number_uuid}",
                json={"assistantId": vapi_assistant_id},
                headers=headers
                ).raise_for_status()
                
                new_assistant.attached_Number = assistant.attached_Number
                new_assistant.vapi_phone_uuid = new_number_uuid
              
                await new_assistant.save()

                return {
                        "success": True,
                        "id": new_assistant.id,
                        "name": new_assistant.name,
                        "detail": "Assistant created and phone number attached successfully."
                    }
             
           
           
            await new_assistant.save()
            
            return {
                "success": True,
                "id": new_assistant.id,
                "name": new_assistant.name,
                "detail": "Assistant created successfully."
            }

        else:
            vapi_error = response.json()
            error_message = vapi_error.get("message", ["An unknown error occurred"])
            for message in error_message:
                if "forwardingPhoneNumber" in message:
                    raise HTTPException(status_code=400, detail="ForwardingPhoneNumber must be a valid phone number in the E.164 format.")
            
            raise HTTPException(status_code=response.status_code, detail=f"VAPI Error: {response.text}")

    except HTTPException as http_exc:
        raise http_exc
    
    except Exception as e:
        print(f"Exception occurred: {e}")
        raise HTTPException(status_code=400, detail=f"An error occurred while creating the assistant: {str(e)}")

@assistant_router.get("/get-assistants")
async def get_all_assistants(user: Annotated[User, Depends(get_current_user)]):
    try:
        assistants = await Assistant.all().select_related('user')

        if not assistants:
            return []

        assistants_with_user = [
            {
                "id": assistant.id,
                "name": assistant.name,
                "vapi_assistant_id": assistant.vapi_assistant_id,
                "provider": assistant.provider,
                "first_message": assistant.first_message,
                "model": assistant.model,
                "system_prompt": assistant.systemPrompt,
                "knowledge_base": assistant.knowledgeBase,
                "leadsfile": assistant.leadsfile,
                "temperature": assistant.temperature,
                "max_tokens": assistant.maxTokens,
                "transcribe_provider": assistant.transcribe_provider,
                "transcribe_language": assistant.transcribe_language,
                "transcribe_model": assistant.transcribe_model,
                "voice_provider": assistant.voice_provider,
                "voice": assistant.voice,
                "category":assistant.category,
                # "success_evalution": assistant.success_evalution,
                "user": {
                    "id": assistant.user.id,
                    "name": assistant.user.name,
                    "email": assistant.user.email,

                }
            }
            for assistant in assistants
        ]

        return assistants_with_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e}")

#get assistant of user by id
@assistant_router.get("/get-assistants/{user_id}")
async def get_all_assistants(user_id: int, user: Annotated[User, Depends(get_current_user)]):
    try:
        assistants = await Assistant.filter(user__id=user_id).select_related('user')

        if not assistants:
            return []  

        assistants_with_user = [
            {
                "id": assistant.id,
                "name": assistant.name,
                "vapi_assistant_id": assistant.vapi_assistant_id,
                "provider": assistant.provider,
                "first_message": assistant.first_message,
                "model": assistant.model,
                "system_prompt": assistant.systemPrompt,
                "knowledge_base": assistant.knowledgeBase,
                "leadsfile": assistant.leadsfile,
                "temperature": assistant.temperature,
                "max_tokens": assistant.maxTokens,
                "transcribe_provider": assistant.transcribe_provider,
                "transcribe_language": assistant.transcribe_language,
                "transcribe_model": assistant.transcribe_model,
                "voice_provider": assistant.voice_provider,
                "voice": assistant.voice,
                "category": assistant.category,
                # "success_evalution": assistant.success_evalution,
                "user": {
                    "id": assistant.user.id,
                    "name": assistant.user.name,
                    "email": assistant.user.email,
                }
            }
            for assistant in assistants
        ]
         
        # print(assistants_with_user) 
        return assistants_with_user
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@assistant_router.get("/get-admin-assistants")
async def get_admin_assistants(user: Annotated[User,Depends(get_admin)]):
    try:
        assistants = await Assistant.filter().all()
        if not assistants:
            return []

        return assistants
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred: {e}")
    
@assistant_router.get("/get-admin-assistants/{id}")
async def get_admin_assistants(id: int):
    assistant = await Assistant.get_or_none(id=id)
    if not assistant:
        return[]
    try:
        url = f"https://api.vapi.ai/assistant/{assistant.vapi_assistant_id}"

       
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers())

        if response.status_code == 200:
            assistant_data = response.json()

            assistant_detail = {
                "id": assistant_data.get("id"),
                "name": assistant_data.get("name"),
                "model": assistant_data.get("model", {}).get("model"),
                "provider": assistant_data.get("model", {}).get("provider"),
                "maxTokens": assistant_data.get("model", {}).get("maxTokens"),
                "temperature": assistant_data.get("model", {}).get("temperature"),
                "knowledgeBase": assistant_data.get("model", {}).get("knowledgeBase", {}).get("fileIds", []),
                "systemPrompt": assistant_data.get("model", {}).get("messages", [{}])[0].get("content"), 
                 # "systemPrompt": assistant_data.get("analysisPlan", {}).get("summaryPrompt"), 
                "first_message" : assistant_data.get("firstMessage"),
                "category":assistant.category,
                # Transcriber info
                "transcribe_model": assistant_data.get("transcriber", {}).get("model"),
                "transcribe_language": assistant_data.get("transcriber", {}).get("language"),
                "transcribe_provider": assistant_data.get("transcriber", {}).get("provider"),
                # voice
                "voice": assistant_data.get("voice", {}).get("voiceId"),
                "voice_provider": assistant_data.get("voice", {}).get("provider"),
                #function
                "dialKeypadEnabled": assistant_data.get("dialKeypadEnabled", False), 
                "endCallFunctionEnabled": assistant_data.get("endCallMessage") is not None,  
                "forwardingPhoneNumber": assistant_data.get("forwardingPhoneNumber", ""),
                "endCallPhrases": assistant_data.get("endCallPhrases",""),
                

                #Advanced
                "silenceTimeoutSeconds": assistant_data.get("silenceTimeoutSeconds"),
                "hipaaEnabled": assistant_data.get("hipaaEnabled"),
                "audioRecordingEnabled": assistant_data.get("artifactPlan", {}).get("recordingEnabled", False),  
                "videoRecordingEnabled": assistant_data.get("artifactPlan", {}).get("videoRecordingEnabled", False), 
                "maxDurationSeconds": assistant_data.get("maxDurationSeconds"),
                "interruptionThreshold": assistant_data.get("stopSpeakingPlan", {}).get("numWords", 0),  
                "responseDelay": assistant_data.get("startSpeakingPlan", {}).get("waitSeconds", 0),  
                "llmRequestDelay": assistant_data.get("startSpeakingPlan", {}).get("transcriptionEndpointingPlan", {}).get("onPunctuationSeconds", 0),  
                "clientMessages": assistant_data.get("clientMessages", []),
                "serverMessages": assistant_data.get("serverMessages", []),
                "endCallMessage": assistant_data.get("endCallMessage"),
                "idleMessages": assistant_data.get("messagePlan", {}).get("idleMessages", []),
                "idleTimeoutSeconds": assistant_data.get("messagePlan", {}).get("idleTimeoutSeconds"),
                "idleMessageMaxSpokenCount": assistant_data.get("messagePlan", {}).get("idleMessageMaxSpokenCount"),
              
                # Analysis Plan
                "summaryPrompt": assistant_data.get("analysisPlan", {}).get("summaryPrompt"),
                "successEvaluationPrompt": assistant_data.get("analysisPlan", {}).get("successEvaluationPrompt"),
                "structuredDataPrompt": assistant_data.get("analysisPlan", {}).get("structuredDataPrompt"),
                 
                
            }

            return assistant_detail

        else:
            return []
        
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while making the request: {e}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"r occurred: {e}")

# @assistant_router.put("/update_admin_assistants/{id}")
# async def update_admin_assistant(id: int, assistant: AdminAssistantUpdate, user: Annotated[User, Depends(get_admin)]):
#     try:
#         existing_assistant = await Assistant.get_or_none(id=id)
#         if not existing_assistant:
#             raise HTTPException(status_code=400, detail="Assistant not found")

#         existing_assistant.name = assistant.name
#         existing_assistant.provider = assistant.provider
#         existing_assistant.first_message = assistant.first_message
#         existing_assistant.model = assistant.model
#         existing_assistant.systemPrompt = assistant.systemPrompt
#         existing_assistant.knowledgeBase = assistant.knowledgeBase
#         existing_assistant.temperature = assistant.temperature
#         existing_assistant.maxTokens = assistant.maxTokens
#         existing_assistant.transcribe_provider = assistant.transcribe_provider
#         existing_assistant.transcribe_language = assistant.transcribe_language
#         existing_assistant.transcribe_model = assistant.transcribe_model
#         existing_assistant.voice_provider = assistant.voice_provider
#         existing_assistant.forwardingPhoneNumber = assistant.forwardingPhoneNumber
#         existing_assistant.voice = assistant.voice
#         existing_assistant.endCallPhrases = assistant.endCallPhrases
#         existing_assistant.category = assistant.category
#         existing_assistant.voice_model = assistant.voice_model
#         await existing_assistant.save()

#         #Update assistant in Vapi
#         payload_data = await admin_add_payload(assistant)
#         vapi_assistant_id = existing_assistant.vapi_assistant_id
#         vapi_url = f"{os.environ.get('VAPI_URL')}/{vapi_assistant_id}"

#         response = requests.patch(vapi_url, json=payload_data, headers=get_headers())
#         if response.status_code not in [200, 201]:
#             vapi_error = response.json()
#             msgs = vapi_error.get("message", ["An unknown error occurred"])
#             for m in msgs:
#                 if "forwardingPhoneNumber" in m:
#                     raise HTTPException(status_code=400, detail="ForwardingPhoneNumber must be a valid E.164 number.")
#             raise HTTPException(status_code=response.status_code, detail=f"VAPI update failed: {', '.join(msgs)}")

#         if assistant.attached_Number:
#             new_number_uuid = None
#             db_num = await PurchasedNumber.filter(phone_number=assistant.attached_Number).first()
#             if not db_num:
#                 vv = await user_has_vv_number(user.id, assistant.attached_Number)
#                 if vv:
#                     vv_ph = await AdminPurchasedNumber.filter(phone_number=assistant.attached_Number).first()
#                     new_number_uuid = vv_ph.vapi_phone_uuid
#                 else:
#                     raise HTTPException(status_code=403, detail="You are not allowed to use this number")
#             else:
#                 new_number_uuid = db_num.vapi_phone_uuid

#             prev = await Assistant.filter(vapi_phone_uuid=new_number_uuid).first()
#             if prev:
#                 prev.vapi_phone_uuid = None
#                 prev.attached_Number = None
#                 await prev.save()

#             requests.patch(
#                 f"https://api.vapi.ai/phone-number/{new_number_uuid}",
#                 json={"assistantId": vapi_assistant_id},
#                 headers=get_headers()
#             ).raise_for_status()


#             if db_num:
#                 db_num.attached_assistant = existing_assistant.id
#                 await db_num.save()

#             existing_assistant.attached_Number = assistant.attached_Number
#             existing_assistant.vapi_phone_uuid = new_number_uuid
#             await existing_assistant.save()

#         return {
#             "success": True,
#             "id": existing_assistant.id,
#             "name": existing_assistant.name,
#             "detail": "Assistant updated successfully."
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         raise HTTPException(status_code=500, detail=f"Internal error: {e}")

@assistant_router.get("/get-user-assistants")
async def get_all_assistants(user: Annotated[User, Depends(get_current_user)]):

    try:
        # assistants = await Assistant.filter(user=user).all().order_by("id")
        # company = await Company.get(id=user.id)
        assistants = await Assistant.filter(user=user).all().order_by("id")
        if not assistants:
            return []

        return assistants
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{str(e)}")
    
@assistant_router.get("/get-assistant/{assistant_id}")
async def get_assistant(assistant_id: int,user: Annotated[User, Depends(get_current_user)]):
    try:
         assistant = await Assistant.get(id=assistant_id)
         if not assistant:
             return []
         return assistant
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e}")
    
@assistant_router.delete("/assistants/{assistant_id}")
async def delete_assistant(assistant_id: int, user: Annotated[User, Depends(get_current_user)]):
    try:
        assistant = await Assistant.get_or_none(id=assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
        
        # if assistant.vapi_phone_uuid:
        #     requests.patch(
        #         f"https://api.vapi.ai/phone-number/{assistant.vapi_phone_uuid}",
        #         json={"assistantId": None},
        #         headers=get_headers()
        #     ).raise_for_status()
        
        # phone_number = None
        # if assistant.attached_Number:
        #     phone_number = await PurchasedNumber.get_or_none(attached_assistant=assistant_id)

        # if phone_number:
        #     await PurchasedNumber.filter(attached_assistant=assistant_id).update(attached_assistant=None)
 
        vapi_assistant_id = assistant.vapi_assistant_id
        vapi_url = f"{os.environ['VAPI_URL']}/{vapi_assistant_id}"
        response = requests.delete(vapi_url, headers=get_headers())

        if response.status_code in [200, 201]:
       
            await assistant.delete()
            return {
                "success": True,
                "detail": "Assistant has been deleted."
            }
        else:
            raise HTTPException(status_code=400, detail=f"VAPI delete failed with status {response.status_code}: {response.text}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e}")

@assistant_router.put("/update_assistant/{assistant_id}")
async def update_assistant(assistant_id: str, assistant: AssistantCreate, user: Annotated[User, Depends(get_current_user)]):
    try:
        existing_assistant = await Assistant.get_or_none(id=assistant_id)
        if not existing_assistant:
            raise HTTPException(status_code=404, detail='Assistant not found')
        existing_assistant.name = assistant.name
        existing_assistant.provider = assistant.provider
        existing_assistant.first_message = assistant.first_message
        existing_assistant.model = assistant.model
        existing_assistant.systemPrompt = assistant.systemPrompt
        existing_assistant.knowledgeBase = assistant.knowledgeBase
        existing_assistant.temperature = assistant.temperature
        existing_assistant.maxTokens = assistant.maxTokens
        existing_assistant.transcribe_provider = assistant.transcribe_provider
        existing_assistant.transcribe_language = assistant.transcribe_language
        existing_assistant.transcribe_model = assistant.transcribe_model
        existing_assistant.voice_provider = assistant.voice_provider
        existing_assistant.voice = assistant.voice
        existing_assistant.draft = assistant.draft
        existing_assistant.assistant_toggle = assistant.assistant_toggle
        existing_assistant.forwardingPhoneNumber = assistant.forwardingPhoneNumber
        existing_assistant.endCallPhrases = assistant.endCallPhrases
        existing_assistant.leadsfile = assistant.leadsfile
        existing_assistant.category = assistant.category
        existing_assistant.voice_model = assistant.voice_model
        existing_assistant.languages = assistant.languages
        payload_data =await user_add_payload(assistant,user)
        vapi_assistant_id = existing_assistant.vapi_assistant_id
        vapi_url = f"{os.environ.get('VAPI_URL')}/{vapi_assistant_id}"
        
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(vapi_url, json=payload_data, headers=get_headers())
            
            if response.status_code not in [200, 201]:
                    vapi_error = response.json()
                    error_messages = vapi_error.get("message", ["An unknown error occurred"])
                    for message in error_messages:
                        if "forwardingPhoneNumber" in message:
                            raise HTTPException(
                                status_code=400,
                                detail="ForwardingPhoneNumber must be a valid phone number in the E.164 format. "
                            )
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"VAPI update failed: {', '.join(error_messages)}"
                    )
            
            if assistant.attached_Number:
                print("--------",assistant.attached_Number )
                new_number_uuid = None
                new_phonenumber = await PurchasedNumber.filter(phone_number = assistant.attached_Number).first()
                print("new_phonenumber", new_phonenumber.vapi_phone_uuid)
                if new_phonenumber:
                   new_number_uuid = new_phonenumber.vapi_phone_uuid
                isNumberAttachedWithPreviousAssistant = await Assistant.filter(vapi_phone_uuid = new_number_uuid, user = user).first()
            
                print("-=================", new_number_uuid)
                requests.patch(
                    f"https://api.vapi.ai/phone-number/{new_number_uuid}",
                    json={"assistantId": vapi_assistant_id},
                    headers=get_headers()
                ).raise_for_status()
                 
                if isNumberAttachedWithPreviousAssistant:
                    isNumberAttachedWithPreviousAssistant.vapi_phone_uuid = None
                    isNumberAttachedWithPreviousAssistant.attached_Number = None
                    await isNumberAttachedWithPreviousAssistant.save() 
                

                
                existing_assistant.attached_Number = assistant.attached_Number
                existing_assistant.vapi_phone_uuid = new_number_uuid
              
                await existing_assistant.save()
           
        await existing_assistant.save()
 

        return {
            "success": True,
            "id": existing_assistant.id,
            "name": existing_assistant.name,
            "detail": "Assistant updated successfully."
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Exception occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred. Please try again later.")
  
@assistant_router.post("/attach-number-to-assistant")
async def attach_number_to_assistant(request: AttachNumberRequest, user: User = Depends(get_current_user)):
    try:
        assistant = await Assistant.get(id=request.assistant_id, user=user)
        phonenumber = await PurchasedNumber.get(phone_number=request.phone_number)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        requests.patch(
            f"https://api.vapi.ai/phone-number/{phonenumber.vapi_phone_uuid}",
            json={"assistantId": assistant.vapi_assistant_id},
            headers=get_headers()
        ).raise_for_status()
        
        assistant.attached_Number = request.phone_number
        assistant.vapi_phone_uuid = phonenumber.vapi_phone_uuid
        phonenumber.attached_assistant = assistant.id
        await assistant.save()
        await phonenumber.save()

        return {
            "success": True,
            "detail": f"Phone number {request.phone_number} attached successfully to assistant {assistant.name}",
            "attached_assistant": assistant.id
        }

    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=400, detail=f"An error occurred: {e}")
    


# @assistant_router.post("/detach-number-from-assistant")
# async def detach_number_from_assistant(request: AttachNumberRequest, user: User = Depends(get_current_user)):
#     try:
#         phonenumber = await PurchasedNumber.get(phone_number=request.phone_number)
#         assistants = await Assistant.filter(user=user, attached_Number=phonenumber.phone_number).all()

#         if not assistants:
#             raise HTTPException(status_code=404, detail="No assistants found using this phone number")

#         requests.patch(
#             f"https://api.vapi.ai/phone-number/{phonenumber.vapi_phone_uuid}",
#             json={"assistantId": None},
#             headers=get_headers()
#         ).raise_for_status()
#         for assistant in assistants:
#             assistant.attached_Number = None
#             assistant.vapi_phone_uuid = None
#             await assistant.save()
#             await Logs.create(
#                 user=user,
#                 message=f"Detached phone number {request.phone_number} from assistant {assistant.name}",
#                 short_message="detach_number"
#             )

#         phonenumber.attached_assistant = None
#         await phonenumber.save()

#         return {
#             "success": True,
#             "detail": f"Phone number {request.phone_number} detached successfully from {len(assistants)} assistant(s)"
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"An error occurred: {e}")

@assistant_router.post("/assistant-call/{vapi_assistant_id}/{lead_id}")
async def assistant_call(
    vapi_assistant_id: str,
    lead_id: int,
    user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks 
):
    try:

        # user_active = await user_criteria_approved(user)
            
        # if not user_active:
        #         return {"success": False , "detail" : "You haven't completed criteria yet. If you have completed, please wait for admin approval."}
        
        
        # process = await can_process(user.id)
        
        
        # if not process:
        #     balance = await balance_count(user.id)
        #     if balance < 11:
        #         print("Insufficient balance, skipping...")
        #         return {"success" : False, "detail": "Insufficient balance. Can't Call"}
        # if process:
        #     print("have free trial and calling now ")
        #     total_call_duration = await get_total_call_duration(main_admin.id)
        #     print(f"total call minutes {total_call_duration}")
            
        #     setting = await VVadminSetting.filter(user_id=user.id).first()
        #     default_setting = await DefaultSettings.first()

        #     if setting and setting.max_call_limit_free_trial is not None:
        #         max_call_limit = setting.max_call_limit_free_trial
        #     elif default_setting and default_setting.max_call_limit_free_trial is not None:
        #         max_call_limit = default_setting.max_call_limit_free_trial
        #     else:
        #         max_call_limit = 2000 
            
        #     print(f"The max call limit in free trail is {max_call_limit}")
        #     if total_call_duration > max_call_limit:
        #         print("exceed the limit free minutes in trial")
        #         return {
        #             "success":False,
        #             "detail":"You have exceed the limit of free minutes in trial"
        #         }
        #     else:
        #         print("have remaining call minutes in free trial")
        max_call_duration = 300
        user_settings = await SuperAdminSetting.filter(user=user).first()   
        default_setting = await DefaultSettings.first()

        if user_settings:
               max_call_duration = user_settings.max_call_duration
        else:
            max_call_duration = default_setting.max_call_duration
        print("max_call_duration",max_call_duration)
        low_balance_for_call = minimum_balance_for_call(max_call_duration)  
        print("low_balance_for_call",low_balance_for_call)  
        balance = await balance_count(user.id)
        if balance < low_balance_for_call:
            print("Insufficient balance, skipping...")
            return {"success" : False, "detail": "Insufficient balance. Can't Call"}   

        payment_method = await has_payment_method(user)
        if not payment_method:
           return {
                "success":False,
                "detail": f"Unable to make a call. You should have an active payment method first.",
            }
        timezone = pytz.timezone("America/Los_Angeles")  

        call_limit = 30
        # setting = await VVadminSetting.filter(user=main_admin).first()
        # setting = await VVadminSetting.filter(user=user).first()
        # defaultSetting = await DefaultSettings.filter().first()

        if user_settings:
            call_limit = user_settings.max_calls
        else:
            call_limit = default_setting.max_calls
        print("call_limit",call_limit)

        today = datetime.now(timezone).date()
        tomorrow = today + timedelta(days=1)

        today_start = datetime.combine(today, time.min, tzinfo=timezone)
        tomorrow_end = datetime.combine(tomorrow, time.max, tzinfo=timezone)

        calls_count = await CallLog.filter(
            user=user,
            call_started_at__gte=today_start,
            call_started_at__lt=tomorrow_end
        ).count()
        print("calls_count", calls_count)
        if calls_count >= call_limit:
            return {
                "success": False,
                "detail": "Daily call limit exceeded."
            }
       


        assistant = await Assistant.get_or_none(vapi_assistant_id=vapi_assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        lead = await Lead.get_or_none(id=lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if lead.dnc:
            print("lead in dnc crietria")
            return {
           "success": False,
             "detail": "Unable to call. The phone number you are trying to call is listed on the Do Not Call (DNC) registry."
}

        mobile_no = lead.mobile if lead.mobile.startswith('+') else f"+1{lead.mobile}"

        # Get phone number for user
        # result = await get_user_phone_number(user_id=user.id)
        # if result:
        #     print(f"Phone: {result['phone_number']}")
        # else:
        #     print("User not authorized or no numbers available")

        
        # Check phone number availability
        #  and (not result or result['phone_number'] is None):
        if assistant.attached_Number is None:
            return {"success": False, "detail": "Unable to call! No Number Attached with this Assistant"}
        
        # Assign the phone number to use
        phone_uuid = assistant.vapi_phone_uuid
        # phone_uuid = result['vapi_phone_uuid'] if result and result['vapi_phone_uuid'] is not None else assistant.vapi_phone_uuid


         

        # if setting:
        #     call_max_duration = setting.max_call_duration if setting.max_call_duration is not None else (defaultSetting.max_call_duration if defaultSetting and defaultSetting.max_call_duration is not None else 150)
        # else:
        #     call_max_duration = defaultSetting.max_call_duration if defaultSetting and defaultSetting.max_call_duration is not None else 150

        # Ensure minimum duration of 150 seconds
        call_max_duration = max_call_duration if max_call_duration > 150 else 150
        print(f"the max call duration is {call_max_duration}")
        
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
        
        call_url = "https://api.vapi.ai/call"
        payload = {
            "name": "From AIBC",
            "assistantId": assistant.vapi_assistant_id,
            "customer": {
                "numberE164CheckEnabled": True,
                "extension": None,
                "number": mobile_no,
            },
            "phoneNumberId": phone_uuid,
            "assistantOverrides": {
                "variableValues": {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "email": lead.email,
                    "mobile_no": mobile_no,
                    "add_date": lead.add_date.isoformat() if isinstance(lead.add_date, (date, datetime)) else None,
                    "custom_field_01": custom_field_01,
                    "custom_field_02": custom_field_02,
                },
                "maxDurationSeconds": call_max_duration
            }
        }


        # status =await update_assistant_to_inculde_message(mobile_no,assistant)
        # print(f"Updated Assitant Message: {status}")
         
        print(f"This is the payload: {payload} ")
        response = requests.post(call_url, json=payload, headers=get_headers())

        if response.status_code in [200, 201]:
     
            vapi_response_data = response.json()
            call_id = vapi_response_data.get("id")
            started_at = vapi_response_data.get("createdAt")
            first_name = vapi_response_data.get("assistantOverrides", {}).get("variableValues", {}).get("first_name")
            last_name = vapi_response_data.get("assistantOverrides", {}).get("variableValues", {}).get("last_name")
            customer_name = f"{first_name} {last_name}"  
            customer_number = lead.mobile

            if not call_id:
                raise HTTPException(status_code=400, detail="No callId found in the VAPI response.")

            # new_call_log = CallLog(
            #     user=user,
            #     call_id=call_id,
            #     call_started_at=started_at,
            #     customer_name=customer_name,
            #     customer_number=customer_number,
            #     lead_id=lead_id
            # )
            # await new_call_log.save()

            # background_tasks.add_task(get_call_details, call_id=call_id, delay=call_max_duration+60 , lead_id = lead_id , user_id =user.id)

            return {
                "success": True,
                "detail": "Call initiated successfully",
                "vapi_response": vapi_response_data
            }

        else:
          vapi_error = response.json()
          error_message = vapi_error.get("message", ["An unknown error occurred"])

          for message in error_message:
                if "customer.number" in message:
                    concise_error = (
                        "The customer's phone number is invalid. "
                        "Please ensure it is in the correct E.164 format with the country code (e.g., US: +1)."
                    )
                    return {"success": False, "detail": concise_error}

                elif "phoneNumber.fallbackDestination.number" in message:
                    concise_error = (
                        "The fallback destination phone number is invalid. "
                        "Ensure it is in E.164 format, including the country code."
                    )
                    return {"success": False, "detail": concise_error}

          return {
                "success": False,
                "detail": vapi_error.get("message", "An unknown error occurred.")
            }

    except Exception as e:
        print(f"Error occurred in assistant_call: {repr(e)}")
        raise HTTPException(status_code=400, detail=f" {repr(e)}")

# @assistant_router.post("/assistant-toggle")
# async def assistant_toggle(
#     request: AssistantToggle, 
#     user: User = Depends(get_current_user),
# ):
#     try:
        
#         assistant = await Assistant.filter(id=request.id).select_related('user').first()
        
#         if not assistant:
#             raise HTTPException(status_code=404, detail="Assistant not found")
        
#         assistant_user = assistant.user
    

#         company_users = await User.filter(company_id=main_admin_company_id).all()
#         company_user_ids = [u.id for u in company_users]
        
#         existing_assistants = await Assistant.filter(
#             user_id__in=company_user_ids, 
#             category=assistant.category, 
#             assistant_toggle=True
#         ).all()
        
#         assistant_count = len(existing_assistants)
        
#         if existing_assistants:
#             print(f"Existing assistant count: {assistant_count}")
#         else:
#             print(f"No existing assistants, count: {assistant_count}")
        
#         if request.assistant_toggle:
#             await Assistant.filter(
#                 user_id__in=company_user_ids,
#                 category=assistant.category
#             ).exclude(id=request.id).update(assistant_toggle=False)
        
#         assistant.assistant_toggle = request.assistant_toggle
#         await assistant.save()

#         return {"success": True, "detail": "Assistant status updated successfully"}

#     except Exception as e:
#         return {"error": True, "detail": f"{str(e)}"}
    
@assistant_router.post("/demo-phone-call/{vapi_assistant_id}/{number}")
async def assistant_call(
    vapi_assistant_id: str,
    number: str, 
    data: DataForCallDemo,
    background_tasks: BackgroundTasks,
    name : Optional[str] = None,
):
    try:
        print("-------------demo calll")
        user_id=os.getenv("DEMO_USER_ID")
        user=  await User.get_or_none(id=user_id)
        main_admin=  await User.get_or_none(id=user_id)
        vapi_assis_id = ''
        vapi_phone_uuid=''
        # assistant = await Assistant.filter(user=user).first()
        
        if name:
            assistant = await Assistant.filter(name=name,user=user).first()
            if assistant is None:
               return {"success" : False, "detail":f"Assistant with name {name} not found."}
            if assistant:
               vapi_assis_id = assistant.vapi_assistant_id
               vapi_phone_uuid = assistant.vapi_phone_uuid
            #    if vapi_phone_uuid is None:
            #       return {"success" : False, "detail":f"There is no number attached with assistant {name}"}
        else:
            assistant = await Assistant.filter(user=user).first()
            if assistant:
                vapi_assis_id = assistant.vapi_assistant_id
                vapi_phone_uuid = assistant.vapi_phone_uuid
                # if vapi_phone_uuid is None:
                #     return {"success" : False, "detail":f"There is no number attached with assistant"}
            
          
        if not vapi_phone_uuid:
           phoneNumber = await PurchasedNumber.filter(user=user).first()
           if not phoneNumber:
               return {"success" : False, "detail":f"There is no number attach whit this assistant."}
           else:
               vapi_phone_uuid = phoneNumber.vapi_phone_uuid
               
        vapi_assis_id = vapi_assis_id if vapi_assis_id else vapi_assistant_id
        mobile_no = number if number.startswith('+') else f"+1{number}"
        phoneNumber_id= vapi_phone_uuid if vapi_phone_uuid else "c3a56c9e-a4d6-4b38-b71f-770d7fe5a656"
        call_max_duration = 300
        call_url = "https://api.vapi.ai/call"
        
        
        payload = {
            "name": "From The Helios Ai",
            "assistantId": vapi_assis_id,
            "customer": {
                "numberE164CheckEnabled": True,
                "extension": None,
                "number": mobile_no,
            },
            "phoneNumberId": phoneNumber_id,
            "assistantOverrides": {
                "variableValues": {
                    "first_name": data.first_name,
                    "email": data.email if data.email else None,
                    "mobile_no": mobile_no
           
                },
                "maxDurationSeconds": call_max_duration
            },
        }
        
        # status =await update_assistant_to_inculde_message(mobile_no,assistant)
        # print(f"Updated Assitant Message: {status}")


       
        response = requests.post(call_url, json=payload, headers=get_headers())

        if response.status_code in [200, 201]:
            response_data = response.json()

            call_id = response_data.get("id")
            started_at = response_data.get("createdAt")
            first_name = response_data.get("assistantOverrides", {}).get("variableValues", {}).get("first_name")
            last_name = response_data.get("assistantOverrides", {}).get("variableValues", {}).get("last_name")
            customer_name = f"{first_name}" if first_name  else "Unknown"
            customer_number = mobile_no

            if not call_id:
                raise HTTPException(status_code=400, detail="No callId found in the VAPI response.")

            # new_call_log = CallLog(
            #     user=main_admin,
            #     call_id=call_id,
            #     call_started_at=started_at,
            #     customer_name=customer_name,
            #     customer_number=customer_number,
            # )
            # await new_call_log.save()

            # background_tasks.add_task(get_call_details, call_id=call_id, delay=call_max_duration+60, user_id =user.id)
            # await Demo.create(
            #     name= data.first_name,
            #     email= data.email if data.email else None,
            #     mobile= data.mobile_no,
            # )
            return {
                "success": True,
                "detail": "Call initiated successfully",
                "vapi_response": response_data,
            }

        else:
            error_data = response.json()
            error_message = error_data.get("message", ["An unknown error occurred"])

            if "Twilio Error" in error_message and "Perhaps you need to enable some international permissions" in error_message:
                return {
                    "success": False,
                    "detail": (
                        "Couldn't create the Twilio call. Your account may not be authorized to make international calls to this number. "
                        
                    ),
                }

            for message in error_message:
                if "customer.number" in message:
                    return {
                        "success": False,
                        "detail": (
                            "The customer's phone number is invalid. "
                            "Please ensure it is in the correct E.164 format with the country code (e.g., US: +1)."
                        ),
                    }
                elif "phoneNumber.fallbackDestination.number" in message:
                    return {
                        "success": False,
                        "detail": (
                            "The fallback destination phone number is invalid. "
                            "Ensure it is in E.164 format, including the country code."
                        ),
                    }

            return {"success": False, "detail": error_data.get("message", "An unknown error occurred.")}

    except Exception as e:
        print(f"Error occurred in assistant_call: {repr(e)}")
        raise HTTPException(status_code=400, detail=f"Error occurred: {repr(e)}")
    


# @assistant_router.post("/phone-call")
# async def assistant_call(
#     payload: PhoneCallRequest,
#     background_tasks: BackgroundTasks,
#     request: Request
# ):
#     try:
     


#         user_active = await user_criteria_approved(main_admin)
        
#         if not user_active:
#             return {"success": False, "detail": "You haven't completed criteria yet. If you have completed, please wait for admin approval."}

#         if not main_admin:
#             raise HTTPException(status_code=404, detail="Main admin not found.")

#         process = await can_process(main_admin.id)
#         if not process:
#             balance = await balance_count(main_admin.id)
#             if balance < 11:
#                 return {"success": False, "detail": "Insufficient balance."}

#         if process:
#             total_call_duration = await get_total_call_duration(main_admin.id)
#             setting = await VVadminSetting.filter(user_id=main_admin.id).first()
#             default_setting = await DefaultSettings.first()

#             if setting and setting.max_call_limit_free_trial is not None:
#                 max_call_limit = setting.max_call_limit_free_trial
#             elif default_setting and default_setting.max_call_limit_free_trial is not None:
#                 max_call_limit = default_setting.max_call_limit_free_trial
#             else:
#                 max_call_limit = 2000

#             print(f"max_call limit {max_call_limit}")
#             if total_call_duration > max_call_limit:
#                 return {"success": False, "detail": "Exceed the limit of free minutes in trial"}

#         payment_method = await has_payment_method(main_admin)
#         if not payment_method:
#             return {"success": False, "detail": "Unable to make call. You should have an active payment method first."}

#         timezone = pytz.timezone("America/Los_Angeles")
#         setting = await VVadminSetting.filter(user=main_admin).first()
#         defaultSetting = await DefaultSettings.filter().first()

#         call_limit = setting.max_calls if setting else defaultSetting.max_calls

#         today = datetime.now(timezone).date()
#         tomorrow = today + timedelta(days=1)
#         today_start = datetime.combine(today, time.min, tzinfo=timezone)
#         tomorrow_end = datetime.combine(tomorrow, time.max, tzinfo=timezone)

#         calls_count = await CallLog.filter(
#             user=main_admin,
#             call_started_at__gte=today_start,
#             call_started_at__lt=tomorrow_end,
#         ).count()

#         if calls_count >= call_limit:
#             return {"success": False, "detail": "Daily call limit exceeded."}
        
#         assistant=None
        
#         if payload.agent_id:
#             assistant = await Assistant.get_or_none(id=payload.agent_id)
            
#             if not assistant:
#                 raise HTTPException(status_code=404, detail="Assistant with provided id not found")
            
#             if assistant.attached_Number is None:
#                 return {"success": False, "detail": "Unable to call! No Number Attached with this Assistant"}
#         else:
#             print("Not agent id is provided so first agent will be use to call ")
        
#         if payload.agent_id in (None, "", " "):
#             assistant = await Assistant.get_or_none(user_id=main_admin.id).first()
#             if not assistant:
#                 raise HTTPException(status_code=404, detail="You first need to create assistant")
            
#             # print(assistant.name)
#             # Get phone number for user
#             result = await get_user_phone_number(user_id=main_admin.id)
#             if result:
#                 print(f"Phone: {result['phone_number']}")
#             else:
#                 print("User not authorized or no numbers available")

            
#             # Check phone number availability
#             if assistant.attached_Number is None and (not result or result['phone_number'] is None):
#                 return {"success": False, "detail": "Unable to call! No Number Attached with this Assistant"}
            
#             # Assign the phone number to use
#             phone_uuid = result['vapi_phone_uuid'] if result and result['vapi_phone_uuid'] is not None else assistant.vapi_phone_uuid
            
            
#         mobile_no = payload.number if payload.number.startswith('+') else f"+{payload.number}"
#         print(f"Final mobile number to be sent: {mobile_no}")

#         if setting and setting.max_call_duration is not None:
#             call_max_duration = setting.max_call_duration
#         elif default_setting and default_setting.max_call_duration is not None:
#             call_max_duration = default_setting.max_call_duration
#         else:
#             call_max_duration = 150 

#         call_max_duration = max(call_max_duration, 150)

#         print(f"This is the Max call duration: {call_max_duration}")


#         call_url = "https://api.vapi.ai/call"
#         payload_data = {
#             "name": "From AIBC",
#             "assistantId": assistant.vapi_assistant_id,
#             "customer": {
#                 "numberE164CheckEnabled": True,
#                 "extension": None,
#                 "number": mobile_no,
#             },
#             "phoneNumberId": phone_uuid,
#             "assistantOverrides": {
#                 "variableValues": {
#                     "first_name": payload.first_name,
#                     "last_name": None,
#                     "email": payload.email,
#                     "mobile_no": mobile_no
                    
#                 },
#                 "maxDurationSeconds": call_max_duration
#             },
#         }


#         # status =await update_assistant_to_inculde_message(mobile_no,assistant)
#         # print(f"Updated Assitant Message: {status}")
        
        
#         response = requests.post(call_url, json=payload_data, headers=get_headers())

#         if response.status_code in [200, 201]:
#             response_data = response.json()
#             call_id = response_data.get("id")
#             if not call_id:
#                 raise HTTPException(status_code=400, detail="No callId found in the VAPI response.")

#             new_call_log, created = await CallLog.get_or_create(
#                 call_id=call_id,
#                 defaults={
#                     'user': main_admin,
#                     'call_started_at': response_data.get("createdAt"),
#                     'customer_name': f"{payload.first_name}",
#                     'customer_number': mobile_no,
#                 }
#             )

#             if created:
#                 background_tasks.add_task(get_call_details, call_id=call_id, delay=call_max_duration + 60, user_id=main_admin.id)
#                 return {
#                     "success": True,
#                     "detail": "Call initiated successfully",
#                     "vapi_response": response_data,
#                 }
#             else:
#                 return {
#                     "success": False,
#                     "detail": "This call log already exists."
#                 }

#         else:
#             error_data = response.json()
#             error_message = error_data.get("message", ["An unknown error occurred"])
#             return {"success": False, "detail": error_message}

#     except Exception as e:
#         print(f"Error occurred in assistant_call: {repr(e)}")
#         raise HTTPException(status_code=400, detail=f"Error occurred: {repr(e)}")

# @assistant_router.post("/phone-call/{vapi_assistant_id}/{number}")
# async def assistant_call(
#     vapi_assistant_id: str,
#     number: str,  
#     data: DataForCall,
#     user: Annotated[User, Depends(get_current_user)],
#     background_tasks: BackgroundTasks,
# ):
#     try:
#         async def validate_user_requirements():
#             user_active = await user_criteria_approved(user)
#             if not user_active:
#                 return {"success": False, "detail": "You haven't completed criteria yet. If you have completed, please wait for admin approval."}
            
#             process = await can_process(user.id)
#             if not process:
#                 balance = await balance_count(user.id)
#                 if balance < 11:
#                     return {"success": False, "detail": "Insufficient balance."}
            
#             if process:
#                 # print("have free trial and calling now 111")
#                 total_call_duration = await get_total_call_duration(user.id)                
#                 setting = await VVadminSetting.filter(user_id=user.id).first()
#                 default_setting = await DefaultSettings.first()

#                 if setting and setting.max_call_limit_free_trial is not None:    
#                     max_call_limit = setting.max_call_limit_free_trial
#                 elif default_setting and default_setting.max_call_limit_free_trial is not None:
#                     max_call_limit = default_setting.max_call_limit_free_trial
#                 else:
#                     max_call_limit = 2000 
                
                
#                 print(f"Max all minutes allowed is : {max_call_limit} Mintues used so far :{total_call_duration}")
                
                
#                 if total_call_duration > max_call_limit:
#                     print("exceed the limit of free minutes in trail can't call more")
#                     return {
#                         "success": False,
#                         "detail": "Exceed the limit of free minutes in trial"
#                     }
#                 else:
#                     print(f"in free trial and can use the free minutes")
            
#             payment_method = await has_payment_method(main_admin)
#             if not payment_method:
#                 return {
#                     "success": False,
#                     "detail": "Unable to make call. You should have an active payment method first.",
#                 }
            
#             return None  


#         validation_error = await validate_user_requirements()
#         if validation_error:
#             return validation_error
#         assistant = await Assistant.get_or_none(vapi_assistant_id=vapi_assistant_id)
#         if not assistant:
#             raise HTTPException(status_code=404, detail="Assistant not found")
#         result = await get_user_phone_number(user_id=user.id)
#         if result:
#             print(f"Phone: {result['phone_number']}")
#         else:
#             print("User not authorized or no numbers available")

 
#         if assistant.attached_Number is None and (not result or result['phone_number'] is None):
#             return {"success": False, "detail": "Unable to call! No Number Attached with this Assistant"}
        
#         phone_uuid = result['vapi_phone_uuid'] if result and result['vapi_phone_uuid'] is not None else assistant.vapi_phone_uuid

#         timezone = pytz.timezone("America/Los_Angeles")
#         print("username", user.name, "admin_name", user.name)
        
#         # setting = await VVadminSetting.filter(user=user).first()
#         # defaultSetting = await DefaultSettings.filter().first()
        
#         if setting:
#             print("--===---=")
#             call_limit = setting.max_calls
#             call_max_duration = setting.max_call_duration
#         else:
#             print(",,,,,,,,---=")
#             call_limit = defaultSetting.max_calls
#             call_max_duration = defaultSetting.max_call_duration

#         print("setting", setting.max_calls if setting else defaultSetting.max_calls)
        
#         today = datetime.now(timezone).date()
#         tomorrow = today + timedelta(days=1)
#         today_start = datetime.combine(today, time.min, tzinfo=timezone)
#         tomorrow_end = datetime.combine(tomorrow, time.max, tzinfo=timezone)

#         calls_count = await CallLog.filter(
#             user=user,
#             call_started_at__gte=today_start,
#             call_started_at__lt=tomorrow_end,
#         ).count()
        
#         print("calls count", calls_count, "call_limit", call_limit)
#         if calls_count >= call_limit:
#             return {"success": False, "detail": "Daily call limit exceeded."}

#         # Format mobile number
#         mobile_no = number if number.startswith('+') else f"+1{number}"
#         call_max_duration = call_max_duration if call_max_duration >150 else 150
        
#         # Prepare API call
#         call_url = "https://api.vapi.ai/call"
        
#         payload = {
#             "name": "From AIBC",
#             "assistantId": assistant.vapi_assistant_id,
#             "customer": {
#                 "numberE164CheckEnabled": True,
#                 "extension": None,
#                 "number": mobile_no,
#             },
#             "phoneNumberId": phone_uuid,
#             "assistantOverrides": {
#                 "variableValues": {
#                     "first_name": data.first_name,
#                     "last_name": data.last_name,
#                     "email": data.email,
#                     "mobile_no": mobile_no,
#                     "add_date": data.add_date.isoformat() if isinstance(data.add_date, (date, datetime)) else None,
#                     "custom_field_01": data.custom_field_01,
#                     "custom_field_02": data.custom_field_02,
#                 },
#                 "maxDurationSeconds": call_max_duration
#             },
#         }
        
#         response = requests.post(call_url, json=payload, headers=get_headers())  

#         if response.status_code in [200, 201]:
#             response_data = response.json()

#             call_id = response_data.get("id")
#             started_at = response_data.get("createdAt")
#             first_name = response_data.get("assistantOverrides", {}).get("variableValues", {}).get("first_name")
#             last_name = response_data.get("assistantOverrides", {}).get("variableValues", {}).get("last_name")
#             customer_name = f"{first_name} {last_name}" if first_name and last_name else "Unknown"
#             customer_number = mobile_no
            
#             if not call_id:
#                 raise HTTPException(status_code=400, detail="No callId found in the VAPI response.")

#             new_call_log = CallLog(
#                 user=user,
#                 call_id=call_id,
#                 call_started_at=started_at,
#                 customer_name=customer_name,
#                 customer_number=customer_number,
#             )
#             await new_call_log.save()

#             background_tasks.add_task(get_call_details, call_id=call_id, delay=call_max_duration+60, user_id=user.id)

#             return {
#                 "success": True,
#                 "detail": "Call initiated successfully",
#                 "vapi_response": response_data,
#             }

#         else:
#             error_data = response.json()
#             error_message = error_data.get("message", ["An unknown error occurred"])

#             if "Twilio Error" in error_message and "Perhaps you need to enable some international permissions" in error_message:
#                 return {
#                     "success": False,
#                     "detail": (
#                         "Couldn't create the Twilio call. Your account may not be authorized to make international calls to this number. "
#                     ),
#                 }

#             for message in error_message:
#                 if "customer.number" in message:
#                     return {
#                         "success": False,
#                         "detail": (
#                             "The customer's phone number is invalid. "
#                             "Please ensure it is in the correct E.164 format with the country code (e.g., US: +1)."
#                         ),
#                     }
#                 elif "phoneNumber.fallbackDestination.number" in message:
#                     return {
#                         "success": False,
#                         "detail": (
#                             "The fallback destination phone number is invalid. "
#                             "Ensure it is in E.164 format, including the country code."
#                         ),
#                     }

#             return {"success": False, "detail": error_data.get("message", "An unknown error occurred.")}

#     except Exception as e:
#         print(f"Error occurred in assistant_call: {repr(e)}")
#         raise HTTPException(status_code=400, detail=f"Error occurred: {repr(e)}")





@assistant_router.post("/admin-demo-phone-call/{vapi_assistant_id}/{number}")
async def assistant_call(
    vapi_assistant_id: str,
    number: str,
    data: DataForCallDemo,
):
    assistant = await Assistant.filter(vapi_assistant_id=vapi_assistant_id).first()
    if not assistant:
        return {"success": False, "detail": "Assistant not found."}

    user = await User.filter(id=assistant.user_id).first()

    if not assistant.vapi_phone_uuid:
        phoneNumber = await PurchasedNumber.filter(user=user).first()
        if not phoneNumber:
            return {"success": False, "detail": "There is no number attached with this assistant."}
        vapi_phone_uuid = phoneNumber.vapi_phone_uuid
    else:
        vapi_phone_uuid = assistant.vapi_phone_uuid

    if number.startswith('+') and len(number) >= 10:
        mobile_no = number
    elif number.isdigit() and len(number) >= 10:
        mobile_no = f"+1{number}"
    else:
        return {"success": False, "detail": "Invalid number format. Must include country code or be a valid 10-digit number."}

    payload = {
        "name": "From phono ai",
        "assistantId": vapi_assistant_id,
        "customer": {
            "numberE164CheckEnabled": True,
            "extension": None,
            "number": mobile_no,
        },
        "phoneNumberId": vapi_phone_uuid,
        "assistantOverrides": {
            "variableValues": {
                "first_name": data.first_name,
                "email": data.email if data.email else None,
                "mobile_no": mobile_no
            },
            "maxDurationSeconds": 300
        },
    }

    response = requests.post("https://api.vapi.ai/call", json=payload, headers=get_headers())
    response_data = response.json()

    if response.status_code in [200, 201]:
        return {
            "success": True,
            "detail":"Call initialized",
            "vapi_response": response_data,
        }
    else:
        message = response_data.get("message", "")
        if isinstance(message, list):
            message = " ".join(message)

        if "customer.number" in message:
            return {
                "success": False,
                "detail": "The customer's phone number is invalid. Please ensure it is in E.164 format (with country code, e.g., +1)."
            }

        return {
            "success": False,
            "detail": message or "Call failed."
        }

@assistant_router.put("/update-all-assistants")
async def update_all_assistants():
    assistants = await Assistant.all()  # Retrieve all assistants from the database

    for assistant in assistants:
        url = f"https://api.vapi.ai/assistant/{assistant.vapi_assistant_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=get_headers())
                response.raise_for_status()  # Raises HTTPStatusError for bad responses

            assistant_data = response.json()

            if "model" in assistant_data and "tools" in assistant_data["model"]:
                for tool in assistant_data["model"]["tools"]:
                    if tool.get("type") == "transferCall":
                        for dest in tool.get("destinations", []):
                            dest.pop("transferPlan", None)  # Remove "transferPlan" if exists

                update_response = await client.patch(url, json=assistant_data, headers=get_headers())
                update_response.raise_for_status()

                print(f"Successfully updated assistant {assistant.name}")
            else:
                print(f"Assistant {assistant.name} data is missing 'model' or 'tools'.")

        except httpx.RequestError as e:
            print(f"Request error for assistant {assistant.name}: {e}")
        except httpx.HTTPStatusError as e:
            print(f"HTTP error for assistant {assistant.name}: {e.response.status_code} - {e.response.text}")
        except httpx.DecodingError:
            print(f"Failed to decode JSON response for assistant {assistant.name}")
        except Exception as e:
            print(f"Unexpected error for assistant {assistant.name}: {e}")

    return {"status": "All assistants have been updated."}
