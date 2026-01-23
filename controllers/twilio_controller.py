import datetime
from typing import List,Annotated
from fastapi import Depends, HTTPException,APIRouter
import httpx
from pydantic import BaseModel
from twilio.rest import Client
from tortoise.transactions import in_transaction
import os 
import dotenv
# from helpers.criteria_check import balance_count, has_payment_method,can_buy_number
from helpers.criteria_check import balance_count, has_payment_method
from helpers.jwt_token  import get_admin, get_current_user
from helpers.vapi_helper import get_headers
from models.assistant import Assistant
# from models.defaultSettings import DefaultSettings
# from models.logs import Logs
# from models.paymentMethod import PaymentMethod
from models.defaultSettings import DefaultSettings
from models.purchased_number import PurchasedNumber
# from models.spent import Spent
from models.spent import Spent
from models.super_admin_setting import SuperAdminSetting
from models.user import User
# from models.vv_adminSetting import VVadminSetting


dotenv.load_dotenv()
twilio_router = APIRouter()

# class PhoneNumberRequest(BaseModel):
#     area_code: str

class PurchaseNumberRequest(BaseModel):
    phone_number: List[str]
class RemoveNumberRequest(BaseModel):
    phone_number: str
class PhoneNumberRequest(BaseModel):
    country:str
    area_codes: List[str]  
class PurchaseNumberRequest(BaseModel):
    phone_number: List[str]  

domain = os.getenv("DOMAIN")
VAPI_WEBHOOK_URL = f"{domain}/api/webhooks/vapi"
    

account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
print("account_sid",account_sid)
client = Client(account_sid, auth_token)

@twilio_router.post("/update-all-vapi-server-urls")
async def update_all_vapi_phone_server_urls(
    current_user: User = Depends(get_current_user)  # Restrict to admin
):
    """
    Updates server.url on ALL existing PurchasedNumber records in Vapi using
    the same payload structure as /purchase_phone_number.
    Also sets assistantId to null to ensure assistant-request webhook is triggered.
    """
    numbers = await PurchasedNumber.all()  # Add .filter(...) if you want to limit scope
    if not numbers:
        return {"success": True, "detail": "No purchased numbers found."}

    updated = 0
    failures = []

    async with httpx.AsyncClient() as client:
        for pn in numbers:
            if not pn.vapi_phone_uuid:
                failures.append(f"{pn.phone_number}: Missing vapi_phone_uuid")
                continue

            # Use the exact same structure as in purchase_phone_number
            payload = {
                    "assistantId": None, 

                    "server": {
                        "url": VAPI_WEBHOOK_URL,
                    },
                    # "server": {
                    #     "url": VAPI_WEBHOOK_URL,
                    #     # Optional: add secret if you want Bearer auth from Vapi
                    #     # "secret": os.getenv("VAPI_WEBHOOK_SECRET")
                    # },
            }

            resp = await client.patch(
                f"https://api.vapi.ai/phone-number/{pn.vapi_phone_uuid}",
                json=payload,
                headers=get_headers()
            )

            if resp.status_code in (200, 204):
                updated += 1
                print(f"Success: {pn.phone_number} ({pn.vapi_phone_uuid})")
            else:
                error_text = resp.text[:200] if resp.text else "No response body"
                failures.append(
                    f"{pn.phone_number} ({pn.vapi_phone_uuid}): "
                    f"{resp.status_code} - {error_text}"
                )

    detail = f"Updated {updated} of {len(numbers)} phone numbers."
    if failures:
        detail += f"\nFailures ({len(failures)}): " + "; ".join(failures[:5])
        if len(failures) > 5:
            detail += f" ... and {len(failures)-5} more."

    return {
        "success": updated > 0 or len(numbers) == 0,
        "detail": detail,
        "total": len(numbers),
        "updated": updated,
        "failures": failures
    }
@twilio_router.post("/number_info")
def check_sms_capability(phone_number_sid: str):
    try:
        print("account_sid",account_sid)

        phone_number = client.incoming_phone_numbers(phone_number_sid).fetch()
        if phone_number.sms_enabled:
            return {"sms_capable": True, "phone_number": phone_number.phone_number}
        else:
            return {"sms_capable": False, "phone_number": phone_number.phone_number}
    
    except Exception as e:
        return {"error": str(e)}

@twilio_router.post("/available_phone_numbers")
async def buy_phone_number(request: PhoneNumberRequest, user: Annotated[User, Depends(get_current_user)]):
    available_numbers = []
    
    country = request.country
    for area_code in request.area_codes:
        if country == "CA":
            # Handle Canada
            numbers_for_area_code = client.available_phone_numbers('CA').local.list(area_code=area_code)
        else:
            # Handle United States
            numbers_for_area_code = client.available_phone_numbers("US").local.list(area_code=area_code)

        if numbers_for_area_code:
            for number in numbers_for_area_code:
                available_numbers.append({
                    "friendly_name": number.friendly_name,
                    "phone_number": number.phone_number,
                    "region": number.region,
                    "postal_code": number.postal_code,
                    "iso_country": number.iso_country,
                    "capabilities": number.capabilities
                })

    return available_numbers

@twilio_router.post("/available_phone_numbjjers")
async def get_switzerland_numbers_by_area():
    available_numbers = []
    
    try:
        area_code = '91'
        
        # Build query parameters - THIS IS THE FIX!
        query_params = {
            "limit": 100,
            "area_code": area_code  # Add area_code to query_params
        }
        
        # Get numbers with area code specified
        numbers = client.available_phone_numbers('CH').local.list(**query_params)
        
        # Filter results
        for number in numbers:
            include_number = True
            
            if include_number:
                available_numbers.append({
                    "friendly_name": number.friendly_name,
                    "phone_number": number.phone_number,
                    "region": number.region,
                    "postal_code": number.postal_code,
                    "iso_country": number.iso_country,
                    "capabilities": number.capabilities
                })
        
        return {
            "country": "Switzerland",
            "filters": {
                "area_code": area_code
            },
            "total_numbers": len(available_numbers),
            "numbers": available_numbers
        }
        
    except Exception as e:
        return {"error": f"Failed to fetch Switzerland numbers: {str(e)}"}
    
   
@twilio_router.post("/purchase_phone_number")
async def purchase_phone_number(request: PurchaseNumberRequest, user: Annotated[User, Depends(get_current_user)]):
    try:
        user = await User.filter(id=user.id).first()
        

        # is_in_free_trial = False
        
        # if not user.has_active_subscription:
        #     is_in_free_trial = await can_buy_number(main_admin.id)
        
        # if is_in_free_trial:
        #     total_number = await PurchasedNumber.filter(user_id=main_admin.id).count()
            
        #     if total_number >= 1:
        #         print(f"User in free trial/trial not started - can't buy more than one number. Current count: {total_number}")
        #         return {
        #             "success": False,
        #             "detail": "You can only purchase one number during the free trial period"
        #         }
        #     else:
        #         print(f"Free trial user purchasing first number. Current count: {total_number}")
        
        # elif not user.has_active_subscription:
       
        
        # print("Proceeding with number purchase") 
            
        # if user.has_active_subscription:
        payment_method = await has_payment_method(user)      
        if not payment_method:
                return {
                    "success": False,
                    "detail": "Unable to purchase number. You must have an active payment method first.",
                }
        balance = await balance_count(user.id)
        if balance < 5:
                print("Balance is less than 5")
                return {"success": False, "detail": "Insufficient balance."}

        SMS_URL = os.getenv("SMS_URL")
        async with in_transaction():
            purchased_numbers = []
            for phone_number in request.phone_number:
                print("request.phone_number", request.phone_number)
                purchased_number = client.incoming_phone_numbers.create(
                    phone_number=phone_number
                )
                client.incoming_phone_numbers(purchased_number.sid).update(
                    sms_url=SMS_URL
                )
                print(f"number {purchased_number}")
                attach_payload = {
                    "provider": "twilio",
                    "number": purchased_number.phone_number,
                    "twilioAccountSid": os.environ.get('TWILIO_ACCOUNT_SID'),
                    "twilioAuthToken": os.environ.get('TWILIO_AUTH_TOKEN'),
                    "name": "Twilio Number",
                    "server": {

                        "url": VAPI_WEBHOOK_URL,

                    }
                    # "serverUrl": VAPI_WEBHOOK_URL
                    # "server": {
                    #     "url": VAPI_WEBHOOK_URL  # e.g., "https://yourdomain.com/webhooks/vapi" - set this env var to your backend endpoint
                    #     # Optional: "secret": "your-secret-for-auth" if you want Vapi to send a Bearer token
                    # }
                }
              
                attach_url = os.environ.get('VAPI_ATTACH_PHONE_URL')
                if not attach_url:
                    raise HTTPException(status_code=500, detail="Attachment URL is not configured.")
                
                async with httpx.AsyncClient() as vapiclient:
                    attach_response = await vapiclient.post(attach_url, json=attach_payload, headers=get_headers())
                    attach_data = attach_response.json()
                    print(attach_data)
                    if attach_response.status_code in [200, 201]:
                        vapi_phone_uuid = attach_data.get("id")
                        purchased_entry = await PurchasedNumber.create(
                            user=user,
                            phone_number=purchased_number.phone_number,
                            vapi_phone_uuid=vapi_phone_uuid,
                            friendly_name=purchased_number.friendly_name,
                            region=None, 
                            postal_code=None,
                            iso_country=None,
                        )
                        purchased_numbers.append(purchased_entry.phone_number)
                number_price = 5
                # user_setting = await SuperAdminSetting.filter(user=user).first()
                # if not user_setting:         
                default_setting = await DefaultSettings.first()
                if default_setting:
                    number_price = default_setting.phone_number_price
                
                
                await Spent.create(
                    user=user,
                    spent_money=number_price,
                    description="Purchased a phone number"
                )
            # user_setting = await DefaultSettings.first()
            # main_admin = await User.filter(company_id=user.company_id, main_admin=True, role="company_admin").first()

            # Only add spending record if user is NOT in free trial
            # if not is_in_free_trial and user.has_active_subscription:
            #     await Spent.create(
            #         user=main_admin,
            #         spent_money=user_setting.phone_number_price,
            #         description="Purchased a phone number"
            #     )
            #     log_message = f"Purchased phone numbers: {', '.join(purchased_numbers)}"
            # else:
            #     log_message = f"Purchased phone numbers during free trial: {', '.join(purchased_numbers)}"

            # await Logs.create(
            #     user=user,
            #     message=log_message,
            #     short_message="purchase_number"
            # )
            
            return {
                "success": True,
                "detail": f"Phone numbers {', '.join(purchased_numbers)} purchased and saved successfully!",
                "purchased_numbers": purchased_numbers,
                "sendedNumber": request.phone_number,
                # "free_trial_purchase": is_in_free_trial
            }

    except Exception as e:
        error_message = str(e) 
        print("error_message",error_message)
        raise HTTPException(status_code=400, detail={"error": error_message})

@twilio_router.get("/purchased_numbers")
async def get_purchased_numbers( user: Annotated[User, Depends(get_current_user)]):
    purchased_numbers = await PurchasedNumber.filter(user=user).all().order_by("id")
    
    if not purchased_numbers:
        return {"message": "No purchased numbers found."}

    return [
        {
            "phone_number": pn.phone_number,
            "friendly_name": pn.friendly_name,
            "date_purchased": pn.created_at,
            "user": {
                "username": user.name,
                "email": user.email
            },
            "attached_assistant" : pn.attached_assistant
        }
        for pn in purchased_numbers
    ]


@twilio_router.post("/remove-phone-number")
async def return_phone_number(request: RemoveNumberRequest, user: Annotated[User, Depends(get_current_user)]):
    try:
        purchased_number = client.incoming_phone_numbers.list(phone_number=request.phone_number)
        
        if not purchased_number:
           return {
           "success": False,
           "detail": f"Phone number {request.phone_number} was not found or has already been returned."
                }
        number_to_return = purchased_number[0]

        number_to_return.delete()

        # await Logs.create(
        #     user=user,
        #     message=f"Returned phone number {number_to_return.phone_number}",
        #     short_message="return_number"
        # )
        await PurchasedNumber.filter(phone_number=number_to_return.phone_number).delete()

        return {
            "success": True,
            "detail": f"Phone number {number_to_return.phone_number} has been returned successfully!"
        }

    except Exception as e:
        error_message = str(e)
        raise HTTPException(status_code=400, detail={"error": error_message})

@twilio_router.get("/phone_numbers")
async def get_purchased_numbers(user: Annotated[User, Depends(get_admin)]):
    purchased_numbers = await PurchasedNumber.all().prefetch_related("user")  # Prefetching company data

    if not purchased_numbers:
        return []

    return [
        {
            **dict(pn),
            "phone_number": pn.phone_number,
            "username": pn.user.name if pn.user else None,
            "email": pn.user.email if pn.user else None,
        }
        for pn in purchased_numbers
    ]




