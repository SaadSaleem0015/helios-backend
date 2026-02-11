import datetime
from typing import List, Annotated, Optional
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
from models.twilio_credentials import TwilioCredential
# from models.vv_adminSetting import VVadminSetting
from twilio.base.exceptions import TwilioRestException

dotenv.load_dotenv()
twilio_router = APIRouter()

# class PhoneNumberRequest(BaseModel):
#     area_code: str

class RemoveNumberRequest(BaseModel):
    phone_number: str


class PhoneNumberRequest(BaseModel):
    country: str
    area_codes: List[str]


class PurchaseNumberRequest(BaseModel):
    phone_number: List[str]


class TwilioCredentialCreateUpdate(BaseModel):
    account_sid: str
    auth_token: str
    address_sid: Optional[str] = None

domain = os.getenv("DOMAIN")
VAPI_WEBHOOK_URL = f"https://api.theheliosai.com/api/webhooks/vapi"
# VAPI_WEBHOOK_URL = f"https://540b-175-107-235-43.ngrok-free.app/api/webhooks/vapi"



def validate_twilio_credentials(account_sid: str, auth_token: str, address_sid: Optional[str] = None) -> bool:
    """
    Validate Twilio credentials by attempting to fetch the account resource.
    Returns True if credentials are valid.
    Raises HTTPException (401) on authentication failure.
    Raises HTTPException (500) on unexpected errors.
    """
    if address_sid:
        if not address_sid.startswith("AD"):
            raise HTTPException(
                status_code=400,
                detail="Invalid AddressSid format. It should start with 'AD' followed by 32 hex characters."
            )
    if not account_sid or not auth_token:
        raise HTTPException(
            status_code=400,
            detail="Account SID and Auth Token are required"
        )

    try:
        client = Client(account_sid, auth_token)
        # The cheapest / most reliable auth check
        account = client.api.account.fetch()

        # Optional (almost never needed)
        if account.sid != account_sid:
            raise ValueError("Account SID mismatch (very unexpected)")

        return True

    except TwilioRestException as e:
        # Most common auth failures
        if e.status == 401 or e.code in (20003, 20004, 20005):  # 20003 = auth failed
            raise HTTPException(
                status_code=401,
                detail="Invalid Twilio credentials: Authentication failed. "
                       "Please check your Account SID and Auth Token."
            ) from e

        # Other Twilio errors (rate limit, account suspended, etc.)
        raise HTTPException(
            status_code=e.status or 400,
            detail=f"Twilio API error {e.code}: {e.msg}"
        ) from e

    except Exception as e:
        # Very unexpected failure (network, bug in library, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate Twilio credentials: {str(e)}"
        ) from e

async def get_twilio_client_for_user(user: User) -> Client:
    """
    Resolve Twilio credentials for the given user and return a Twilio client.
    Raises HTTPException if credentials are missing.
    """
    creds = await TwilioCredential.filter(user=user).first()
    if not creds:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "detail": "Twilio credentials not configured for this user. Please add them first.",
            },
        )

    return Client(creds.account_sid, creds.auth_token)


# ==================== Twilio Credentials CRUD Endpoints ====================

@twilio_router.post("/credentials")
async def create_twilio_credentials(
    request: TwilioCredentialCreateUpdate,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Create Twilio credentials for the current user.
    Validates credentials with Twilio API before saving.
    """
    try:
        print("request", request)
        # Validate credentials with Twilio
        validate_twilio_credentials(request.account_sid, request.auth_token, request.address_sid)
        print("credentials validated")
        # Check if credentials already exist for this user
        existing_creds = await TwilioCredential.filter(user=user).first()
        if existing_creds:
            return{
                    "success": False,
                    "detail": "Twilio credentials already exist for this user. Use PUT to update them.",
            }
        
        # Create new credentials
        creds = await TwilioCredential.create(
            user=user,
            account_sid=request.account_sid,
            auth_token=request.auth_token,
            address_sid=request.address_sid,
        )
        
        return {
            "success": True,
            "detail": "Twilio credentials created and validated successfully.",
            "account_sid": creds.account_sid,
            "address_sid": creds.address_sid,
            "created_at": creds.created_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "detail": f"Failed to create Twilio credentials: {str(e)}",
            },
        )


@twilio_router.get("/credentials")
async def get_twilio_credentials(
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Get Twilio credentials for the current user.
    Returns account_sid only (auth_token is sensitive and not returned).
    """
    creds = await TwilioCredential.filter(user=user).first()
    if not creds:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "detail": "Twilio credentials not found for this user.",
            },
        )
    
    return {
        "success": True,
        "account_sid": creds.account_sid,
        "address_sid": creds.address_sid,
        "created_at": creds.created_at,
        "updated_at": creds.updated_at,
    }


@twilio_router.put("/credentials")
async def update_twilio_credentials(
    request: TwilioCredentialCreateUpdate,
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Update Twilio credentials for the current user.
    Validates credentials with Twilio API before updating.
    """
    try:
        # Validate credentials with Twilio
        validate_twilio_credentials(request.account_sid, request.auth_token, request.address_sid)
        
        # Get existing credentials
        creds = await TwilioCredential.filter(user=user).first()
        if not creds:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "detail": "Twilio credentials not found for this user. Use POST to create them.",
                },
            )
        
        # Update credentials
        creds.account_sid = request.account_sid
        creds.auth_token = request.auth_token
        creds.address_sid = request.address_sid
        await creds.save()
        
        return {
            "success": True,
            "detail": "Twilio credentials updated and validated successfully.",
            "account_sid": creds.account_sid,
            "address_sid": creds.address_sid,
            "updated_at": creds.updated_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "detail": f"Failed to update Twilio credentials: {str(e)}",
            },
        )


@twilio_router.delete("/credentials")
async def delete_twilio_credentials(
    user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete Twilio credentials for the current user.
    """
    creds = await TwilioCredential.filter(user=user).first()
    if not creds:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "detail": "Twilio credentials not found for this user.",
            },
        )
    
    await creds.delete()
    
    return {
        "success": True,
        "detail": "Twilio credentials deleted successfully.",
    }


# ==================== End Twilio Credentials CRUD Endpoints ====================

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
async def check_sms_capability(
    phone_number_sid: str,
    current_user: User = Depends(get_current_user),
):
    try:
        client = await get_twilio_client_for_user(current_user)

        phone_number = client.incoming_phone_numbers(phone_number_sid).fetch()
        if phone_number.sms_enabled:
            return {"sms_capable": True, "phone_number": phone_number.phone_number}
        else:
            return {"sms_capable": False, "phone_number": phone_number.phone_number}
    
    except Exception as e:
        return {"error": str(e)}

@twilio_router.post("/available_phone_numbers")
async def search_available_phone_numbers(  # better name: it's search, not buy
    request: PhoneNumberRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    available_numbers = []
    seen_numbers = set()

    client = await get_twilio_client_for_user(user)

    country = request.country.upper().strip()

    for code in request.area_codes:
        code = code.strip()
        if not code.isdigit() or not code:
            continue

        params = {
            "limit": 10,
            "voice_enabled": True,
            # Add sms_enabled if needed: "sms_enabled": True,
        }

        try:
            numbers = []

            if country in ("US", "CA"):
                # NANP: area_code only on .local (mobile doesn't exist)
                if len(code) != 3:
                    continue  # skip invalid area codes
                params["area_code"] = int(code)
                print("params------------", params)
                numbers = client.available_phone_numbers(country).local.list(**params)

            else:
                # International: contains on local
                params["contains"] = code
                numbers = client.available_phone_numbers(country).local.list(**params)

                # Fallback to mobile ONLY if not US/CA and local empty
                if not numbers:
                    numbers = client.available_phone_numbers(country).mobile.list(**params)

            # print(numbers)  # keep for debug if needed, but remove in prod

            for number in numbers:
                phone = number.phone_number
                if phone in seen_numbers:
                    continue
                seen_numbers.add(phone)

                available_numbers.append({
                    "friendly_name": number.friendly_name,
                    "phone_number": phone,
                    "region": number.region or "N/A",
                    "postal_code": number.postal_code or "N/A",
                    "iso_country": number.iso_country or country,
                    "capabilities": number.capabilities,
                    "type": "local",  # for US/CA always local; mobile tag only if fallback used
                    "matched_on": code,
                })

        except Exception as e:
            print(f"Error for {country} / {code}: {str(e)}")
            continue  # skip bad codes, don't crash whole request

    if not available_numbers:
        raise HTTPException(
            status_code=404,  # 404 better than 401 here (not auth issue)
            detail=f"No available numbers found for country {country} with codes: {', '.join(request.area_codes)}. "
        )
    # return available_numbers
    return {
        "success" : True,
        "available_numbers" : available_numbers
    }
@twilio_router.post("/available_phone_numbjjers")
async def get_switzerland_numbers_by_area(
    user: Annotated[User, Depends(get_current_user)],
):
    available_numbers = []
    
    try:
        client = await get_twilio_client_for_user(user)

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
async def purchase_phone_number(
    request: PurchaseNumberRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        user = await User.filter(id=user.id).first()
        # Get Twilio credentials from database
        twilio_creds = await TwilioCredential.filter(user=user).first()
        if not twilio_creds:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "detail": "Twilio credentials not configured for this user. Please add them first.",
                },
            )
        client = await get_twilio_client_for_user(user)
        

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

        async with in_transaction():
            purchased_numbers = []
            for phone_number in request.phone_number:
                print("request.phone_number", request.phone_number)
                if twilio_creds.address_sid:
                    purchased_number = client.incoming_phone_numbers.create(
                        phone_number=phone_number,
                        address_sid=twilio_creds.address_sid
                    )
                else:
                    purchased_number = client.incoming_phone_numbers.create(
                        phone_number=phone_number
                    )
          
                print(f"number {purchased_number}")
                attach_payload = {
                    "provider": "twilio",
                    "number": purchased_number.phone_number,
                    "twilioAccountSid": twilio_creds.account_sid,
                    "twilioAuthToken": twilio_creds.auth_token,
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
                # number_price = 5
                # # user_setting = await SuperAdminSetting.filter(user=user).first()
                # # if not user_setting:         
                # default_setting = await DefaultSettings.first()
                # if default_setting:
                #     number_price = default_setting.phone_number_price
                
                
                # await Spent.create(
                #     user=user,
                #     spent_money=number_price,
                #     description="Purchased a phone number"
                # )
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

    except TwilioRestException as e:  
        if e.code == 21631:
            raise HTTPException(
            status_code=400,
            detail="This international number requires a valid AddressSid due to regulatory rules. "
                   "Please add a compliant address in Twilio Console and provide its SID. "
        )
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
        client = await get_twilio_client_for_user(user)
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




