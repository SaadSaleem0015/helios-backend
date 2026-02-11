import asyncio
from typing import Dict, List, Optional 
from fastapi import APIRouter, HTTPException, Query , Depends , Request
import httpx
from pydantic import BaseModel
from helpers.jwt_token import get_current_user
from models.assistant import Assistant
from datetime import datetime, time, timezone
from models.cal_integration import CalComIntegration
from models.user import User
from tortoise.exceptions import DoesNotExist
from helpers.email import send_email
from zoneinfo import ZoneInfo
# Cal.com Config
CAL_COM_BASE_URL = "https://api.cal.com/v2"
CAL_COM_API_VERSION = "v2"  # or try "2024-08-13" if needed
CAL_COM_API_KEY = "cal_live_8f789cc63e449578f879e88be2d67f1d"

cal_booking_router = APIRouter()


class EventTypeListResponse(BaseModel):
    status: str
    message: Optional[str] = None
    event_types: List[Dict] = []  # [{id, slug, name, ...}]
    default_timezone: Optional[str] = None


class EventValidationRequest(BaseModel):
    api_key: str
    event_type_id: int
    event_slug: str
    time_zone: str


class EventValidationResponse(BaseModel):
    status: str
    message: str
    confirmed: Dict  # {id, slug, timeZone, name?}

class RequestEventTypes(BaseModel):
    api_key: str
async def get_cal_com_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Cal-Api-Version": CAL_COM_API_VERSION,
    }


@cal_booking_router.post("/calcom/event-types", response_model=EventTypeListResponse)
async def get_cal_com_event_types(request: RequestEventTypes):
    """
    Get all Cal.com event types
    """

    api_key = request.api_key

    if not api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")

    headers = await get_cal_com_headers(api_key)

    async with httpx.AsyncClient() as client:
        response = await client.get(
                f"{CAL_COM_BASE_URL}/event-types",
                headers=headers,
                timeout=15.0
            )
        if response.status_code == 403:
                raise HTTPException(
                    status_code=401,
                    detail="Provided API key is invalid or incorrect."
                )
        if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Cal.com API error: {response.text}"
                )
        try:
            

            

            data = response.json()

            updated_data = data.get('data')
            print("Updated data:", updated_data)
            # ---------------------------------------
            # ✅ NEW STRUCTURE HANDLING
            # ---------------------------------------

            event_types = []
            updatedgroups = updated_data["eventTypeGroups"]


            for group in updatedgroups:
                types = group.get("eventTypes", [])
                event_types.extend(types)

            # ---------------------------------------

            if not event_types:
                return EventTypeListResponse(
                    status="warning",
                    message="No event types found. Please create one in Cal.com first.",
                    event_types=[],
                    default_timezone=None
                )

            cleaned_events = []

            for et in event_types:

                timezone = (
                    et.get("timeZone")
                    or et.get("owner", {}).get("timeZone")
                )

                cleaned_events.append({
                    "id": et.get("id"),
                    "slug": et.get("slug"),
                    "name": et.get("title") or et.get("name", "Unnamed"),
                    "length": et.get("length"),
                    "timeZone": timezone
                })

            default_timezone = cleaned_events[0].get("timeZone")

            return EventTypeListResponse(
                status="success",
                event_types=cleaned_events,
                default_timezone=default_timezone
            )

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to Cal.com: {str(e)}"
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal Server Error: {str(e)}"
            )


  
@cal_booking_router.post("/calcom/integration", response_model=EventValidationResponse)
async def save_calcom_integration(
    req: EventValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Save Cal.com integration details for the current authenticated user.
    
    Frontend sends: api_key, event_type_id, slug, time_zone
    No validation against Cal.com — just store the values.
    """
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")

    if req.event_type_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid event type ID")

    if not req.event_slug.strip():
        raise HTTPException(status_code=400, detail="Slug is required")

    if not req.time_zone.strip():
        raise HTTPException(status_code=400, detail="Timezone is required")

    # Optional: basic format check for timezone (very loose)
    if "/" not in req.time_zone and len(req.time_zone) < 3:
        raise HTTPException(status_code=400, detail="Invalid timezone format")

    # Upsert logic: update if exists, create if not
    try:
        integration = await CalComIntegration.get(
            user=current_user,
            event_type_id=req.event_type_id
        )
        # Update existing record
        integration.api_key = req.api_key
        integration.event_slug = req.event_slug
        integration.time_zone = req.time_zone
        # We don't have name/length from frontend → keep old or leave null
        # If frontend starts sending name/length, you can add:
        # integration.event_name = req.event_name or integration.event_name
        # integration.length_minutes = req.length_minutes or integration.length_minutes
        await integration.save()

    except DoesNotExist:
        # Create new record
        integration = await CalComIntegration.create(
            user=current_user,
            api_key=req.api_key,
            event_type_id=req.event_type_id,
            slug=req.event_slug,
            time_zone=req.time_zone,
            # event_name and length_minutes remain null unless frontend sends them
        )

    # Prepare response
    return EventValidationResponse(
        status="success",
        message="Cal.com integration saved successfully",
        confirmed={
            "id": req.event_type_id,
            "slug": req.event_slug,
            "timeZone": req.time_zone,
            "name": None,                # not validated/fetched
            "length_minutes": None,      # not provided
            "integration_id": integration.id,
            "saved_at": integration.updated_at.isoformat() if integration.updated_at else None
        }
    )

@cal_booking_router.patch("/calcom/integration", response_model=EventValidationResponse)
async def update_calcom_integration(
    req: EventValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Jab user "Change" click kare, new key + event + timezone daale aur save kare
    Same validation jaise pehle POST mein thi
    """
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")

    if req.event_type_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid event type ID")

    if not req.event_slug.strip():
        raise HTTPException(status_code=400, detail="Slug is required")

    if not req.time_zone.strip():
        raise HTTPException(status_code=400, detail="Timezone is required")

    try:
        # Update existing
        integration = await CalComIntegration.get(user=current_user)
        integration.api_key = req.api_key
        integration.event_type_id = req.event_type_id
        integration.slug = req.event_slug          # consistent field name
        integration.time_zone = req.time_zone
        await integration.save()

    except DoesNotExist:
        # Agar pehle se nahi tha (rare case), create kar do
        integration = await CalComIntegration.create(
            user=current_user,
            api_key=req.api_key,
            event_type_id=req.event_type_id,
            slug=req.event_slug,
            time_zone=req.time_zone,
        )

    return EventValidationResponse(
        status="success",
        message="Cal.com integration updated successfully",
        confirmed={
            "id": req.event_type_id,
            "slug": req.event_slug,
            "timeZone": req.time_zone,
            "integration_id": integration.id,
            "saved_at": integration.updated_at.isoformat() if integration.updated_at else None
        }
    )






class CalIntegrationStatusResponse(BaseModel):
    is_connected: bool
    api_key_masked: Optional[str] = None          # e.g. "cal_live_8f789cc6********"
    event_type_id: Optional[int] = None
    event_slug: Optional[str] = None
    time_zone: Optional[str] = None
    event_name: Optional[str] = None              # agar store kar rahe ho
    updated_at: Optional[str] = None


def mask_cal_key(key: str) -> str:
    """Safe masking for frontend"""
    if not key or len(key) <= 15:
        return "********"
    return key[:12] + "********"   # cal_live_8f789cc6********


@cal_booking_router.get("/calcom/integration", response_model=CalIntegrationStatusResponse)
async def get_calcom_integration_status(
    current_user: User = Depends(get_current_user)
):
    """
    Frontend pe call karo jab page load ho.
    Agar connected hai → masked key + details dikhao + "Change" button enable karo
    Agar nahi hai → sirf is_connected: false
    """
    try:
        integration = await CalComIntegration.get(user=current_user)

        return CalIntegrationStatusResponse(
            is_connected=True,
            api_key_masked=mask_cal_key(integration.api_key),
            event_type_id=integration.event_type_id,
            event_slug=integration.slug,                    # note: slug field hai model mein
            time_zone=integration.time_zone,
            event_name=getattr(integration, "event_name", None),
            updated_at=integration.updated_at.isoformat() if integration.updated_at else None,
        )
    except DoesNotExist:
        return CalIntegrationStatusResponse(is_connected=False)




class AvailabilityRequest(BaseModel):
    assistantId: str
    date: str | None = None  

class AvailabilitySlot(BaseModel):
    display: str                    
    start_iso: str                 

class AvailabilityResponse(BaseModel):
    success: bool
    timezone: str
    slots: list[AvailabilitySlot]
    message: str















# @cal_booking_router.post("/calcom/availability")
# async def get_availability_for_event(request: AvailabilityRequest):

#     try:
#         integration = await CalComIntegration.get(event_type_id=request.event_type_id)
#     except DoesNotExist:
#         raise HTTPException(404, "Cal.com integration not found")

#     # Today in UTC
#     today = datetime.now(timezone.utc).date()

#     # Get date from request or use today
#     start_date_str = request.start_date or today.isoformat()

#     # Convert string -> date
#     start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

#     # Create proper UTC datetimes
#     start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
#     end_dt = datetime.combine(start_date, time.max, tzinfo=timezone.utc)

#     # ISO 8601 format
#     start_utc = start_dt.isoformat().replace("+00:00", "Z")
#     end_utc = end_dt.isoformat().replace("+00:00", "Z")

#     print("Start:", start_utc)
#     print("End:", end_utc)

#     headers = {
#         "Authorization": f"Bearer {integration.api_key}",
#         "Content-Type": "application/json",
#         "cal-api-version": "2024-09-04"
#     }

#     params = {
#         "eventTypeId": request.event_type_id,
#         "start": start_utc,
#         "end": end_utc,
#         "timeZone": integration.time_zone  
#     }

#     async with httpx.AsyncClient() as client:
#         resp = await client.get(
#             f"{CAL_COM_BASE_URL}/slots",
#             headers=headers,
#             params=params,
#             timeout=20.0
#         )
#         print("Cal.com slots response status:", resp.json())
#         if resp.status_code != 200:
#             error_text = resp.text[:200]
#             raise HTTPException(resp.status_code, f"Cal.com error: {error_text}")

#         cal_data = resp.json()
#         print("Cal.com slots response status:----------------", cal_data)
        
#     slots = []
#     for date_key, slot_list in cal_data.get("data", {}).items():
#         for slot in slot_list:
#             start_iso = slot.get("start")  # e.g. "2026-03-10T10:30:00.000+05:00"
#             if not start_iso:
#                 continue

#             # Parse for nice display
#             try:
#                 dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
#                 display_str = dt.strftime("%A, %B %d at %I:%M %p")
#             except:
#                 display_str = start_iso  # fallback

#             slots.append(AvailabilitySlot(
#                 display=display_str,
#                 start_iso=start_iso
#             ))

#     # Sort by time
#     slots.sort(key=lambda s: s.start_iso)

#     return AvailabilityResponse(
#         success=True,
#         timezone=integration.time_zone,
#         slots=slots[:20],   # limit to avoid huge response
#         message=f"{len(slots)} available slots found in {integration.time_zone}"
#     )


@cal_booking_router.post("/calcom/availability")
async def get_availability_for_event(request: Request):
    payload = await request.json()

    assistant_id = payload.get("message", {}).get("assistant", {}).get("id")
    print("assistant_id", assistant_id)
    date = payload["message"]["toolCalls"][0]["function"]["arguments"]["date"]
    print(date)
    tool_call_id = payload["message"]["toolCalls"][0]["id"]

    if assistant_id:
       assistant = await Assistant.filter(vapi_assistant_id =assistant_id).first()
       if assistant:
          user = await User.filter(id=assistant.user_id).first()
          print("user",user.name)
          if user:
                integration = await CalComIntegration.filter(user=user).first()
                if integration:
                    event_type_id = integration.event_type_id
                else:
                    return {"error": "No Cal.com integration found for this user."}   
                print("event_type_id", event_type_id)
                tz = ZoneInfo(integration.time_zone) 

                today = datetime.now(tz).date()

                start_date_str = date or today.isoformat()

                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

                start_dt = datetime.combine(start_date, time.min).replace(tzinfo=tz)
                end_dt = datetime.combine(start_date, time.max).replace(tzinfo=tz)

                start_iso = start_dt.isoformat()
                end_iso = end_dt.isoformat()


                headers = {
                    "Authorization": f"Bearer {integration.api_key}",
                    "Content-Type": "application/json",
                    "cal-api-version": "2024-09-04"
                }

                params = {
                    "eventTypeId": integration.event_type_id,
                    "start": start_iso,
                    "end": end_iso,
                    "timeZone": integration.time_zone
                }

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{CAL_COM_BASE_URL}/slots",
                        headers=headers,
                        params=params,
                        timeout=20.0
                    )

                cal_data = resp.json()
                slots = []
                for date_key, slot_list in cal_data.get("data", {}).items():
                    for slot in slot_list:
                        start_iso = slot.get("start")  # e.g. "2026-03-10T10:30:00.000+05:00"
                        if not start_iso:
                            continue

                        # Parse for nice display
                        try:
                            dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                            display_str = dt.strftime("%A, %B %d at %I:%M %p")
                        except:
                            display_str = start_iso  # fallback

                        slots.append(AvailabilitySlot(
                            display=display_str,
                            start_iso=start_iso
                        ))

                # Sort by time
                slots.sort(key=lambda s: s.start_iso)
                result_text = f"Found {len(slots)} available slots on {date} in {integration.time_zone}."

                if slots:
                    result_text += "\nHere are the earliest slots:\n"
                    for slot in slots[:10]:  # top 3 dikhao
                        result_text += f"- {slot.display}\n"
                else:
                    result_text += "\nNo slots available on this date."

                # Vapi format mein return
                return {
                    "results": [
                        {
                            "toolCallId": tool_call_id,
                            "result": result_text
                        }
                    ]
                }


@cal_booking_router.post("/book")
async def book_appointment(request: Request):

    payload = await request.json()

    message = payload.get("message", {})
    tool_call = message.get("toolCalls", [{}])[0]

    args = tool_call.get("function", {}).get("arguments", {})

    assistant_id = message.get("assistant", {}).get("id")
    tool_call_id = tool_call.get("id")

    date = args.get("date")                 
    name = args.get("name")
    phone = args.get("phone")
    selected_slot = args.get("selected_slot") 
    reason_for_booking = args.get("reason_for_booking", "")

    print("Booking:", date, selected_slot, name, phone)

    if not all([assistant_id, date, name, phone, selected_slot]):
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": "Missing required booking information."
                }
            ]
        }

    if not phone.startswith("+"):
        phone = "+" + phone


    assistant = await Assistant.filter(vapi_assistant_id=assistant_id).first()

    if not assistant:
        return {"error": "Assistant not found"}

    user = await User.filter(id=assistant.user_id).first()

    if not user:
        return {"error": "User not found"}

    integration = await CalComIntegration.filter(user=user).first()

    if not integration:
        return {"error": "No Cal.com integration found"}


    tz = ZoneInfo(integration.time_zone)


    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        time_obj = datetime.strptime(selected_slot, "%H:%M").time()

        local_dt = datetime.combine(date_obj, time_obj).replace(tzinfo=tz)

        utc_dt = local_dt.astimezone(timezone.utc)

        start_time_iso = utc_dt.isoformat().replace("+00:00", "Z")

    except Exception as e:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": f"Invalid date/time format: {str(e)}"
                }
            ]
        }


    headers1 = {
        "Authorization": f"Bearer {integration.api_key}",
        "Content-Type": "application/json",
        "cal-api-version": "2024-08-13",
    }


    booking_payload = {
        "eventTypeId": integration.event_type_id,
        "start": start_time_iso,
        "attendee": {
            "name": name,
            "timeZone": integration.time_zone,
            "email": user.email or "",
            "phoneNumber": phone,
            "language": "en"
        },
        "metadata": {
            "reason_for_booking": reason_for_booking,
            "source": "vapi"
        }
    }

    print("Cal Booking Payload:", booking_payload)


    async with httpx.AsyncClient() as client:

        resp = await client.post(
            f"{CAL_COM_BASE_URL}/bookings",
            headers=headers1,
            json=booking_payload,
            timeout=20.0
        )


    if resp.status_code not in [200, 201]:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": f"Booking failed: {resp.text}"
                }
            ]
        }


    booking_data = resp.json()
    data = booking_data.get("data", {})

    booking_id = data.get("id")
    booking_uid = data.get("uid")


    # =========================
    # Send Email Notification
    # =========================

    email_subject = "You have a new appointment"

    email_html = f"""
    <h2>New Appointment Scheduled</h2>

    <p><strong>Name:</strong> {name}</p>
    <p><strong>Phone:</strong> {phone}</p>
    <p><strong>Date:</strong> {date}</p>
    <p><strong>Time:</strong> {selected_slot}</p>
    <p><strong>Reason:</strong> {reason_for_booking or "Not provided"}</p>

    <br/>

    <p>Thank you for using <strong>Helios AI Platform</strong>.</p>
    """

    try:
        send_email(
            to_address=user.email,
            subject=email_subject,
            message_html=email_html
        )
    except Exception as e:
        print("Email failed:", e)


    # =========================
    # VAPI RESPONSE
    # =========================

    result_text = f"""
Your appointment has been successfully booked.

📅 Date: {date}
⏰ Time: {selected_slot}
👤 Name: {name}
📞 Phone: {phone}

Booking ID: {booking_uid}

Thank you for choosing Helios AI Platform.
    """


    return {
        "results": [
            {
                "toolCallId": tool_call_id,
                "result": result_text.strip()
            }
        ]
    }
