import asyncio
import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
import httpx
from helpers.jwt_token import get_current_user
from models.hubspot_crm import HubSpotCRM
from models.lead import Lead
from models.user import User
from models.file import File
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import urllib.parse

hubspot_router = APIRouter()

# ── Constants ────────────────────────────────────────────────────────────────
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_API_BASE = "https://api.hubapi.com"
domain = os.getenv("DOMAIN")
REDIRECT_URI = f"{domain}/api/crm/callback/hubspot"  
print(REDIRECT_URI)
# HUBSPOT_CLIENT_ID = "bc1d6fda-e7fd-413a-8c01-4c0b9ce04735"
# HUBSPOT_CLIENT_SECRET = "eea9d800-63cd-4d12-8092-586ef8be21a1"
HUBSPOT_CLIENT_ID = "5d4a3c46-a131-4341-9ebe-40d91bea0398"
HUBSPOT_CLIENT_SECRET = "13f66e01-7448-491a-940f-eeb4cb91a5f4"

# Required scopes for contacts (leads)
SCOPES = "crm.objects.contacts.read"


class HubSpotConnectRequest(BaseModel):
    client_id: str
    client_secret: str


# 1. Check if connected
@hubspot_router.get("/hubspot-available")
async def hubspot_available(current_user: Annotated[User, Depends(get_current_user)]):
    creds = await HubSpotCRM.get_or_none(user=current_user)
    return {
        "success": bool(creds and creds.access_token),
        "message": "HubSpot CRM is connected." if creds else "HubSpot CRM is not connected."
    }


# 2. Start OAuth flow - User provides client_id/secret once (or hardcode if single app)
# @hubspot_router.post("/connect-hubspot")
# async def connect_hubspot(
#     payload: HubSpotConnectRequest,
#     current_user: Annotated[User, Depends(get_current_user)]
# ):
#     # Build authorize URL
#     params = {
#         "client_id": payload.client_id,
#         "redirect_uri": REDIRECT_URI,
#         "scope": SCOPES,
#         "state": str(current_user.id)  # Anti-CSRF: pass user ID
#     }

#     auth_url = f"{HUBSPOT_AUTH_URL}?{urllib.parse.urlencode(params)}"

#     return {
#         "success": True,
#         "authorize_url": auth_url,
#         "message": "Redirect user to this URL to connect HubSpot CRM"
#     }

@hubspot_router.get("/connect-hubspot")  # ya POST without payload
async def connect_hubspot(current_user: Annotated[User, Depends(get_current_user)]):
    params = {
        "client_id": HUBSPOT_CLIENT_ID,  # ← Tumhara fixed
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": str(current_user.id)  # ← Important!
    }
    auth_url = f"{HUBSPOT_AUTH_URL}?{urllib.parse.urlencode(params)}"
    
    return {
        "success": True,
        "authorize_url": auth_url,
        "message": "Redirect user to this URL"
    }

# 3. Callback - HubSpot redirects here with code
@hubspot_router.get("/callback/hubspot")
async def hubspot_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None)
):
    try:
        # Validate state (user ID)
        user_id = int(state) if state else None
        user = await User.get_or_none(id=user_id)
        if not user:
            raise HTTPException(400, "Invalid state/user")

        # Exchange code for tokens (need client_id/secret - assume global or fetch from temp storage; for demo, replace)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                HUBSPOT_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": HUBSPOT_CLIENT_ID,       # ← Replace or store/fetch per user/app
                    "client_secret": HUBSPOT_CLIENT_SECRET  # ← Replace or store/fetch
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            resp.raise_for_status()
            tokens = resp.json()

        await HubSpotCRM.update_or_create(
            user=user,
            defaults={
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "expires_at": datetime.utcnow() + timedelta(seconds=tokens["expires_in"]),
                "hub_id": tokens.get("hub_id")  # Optional from metadata if needed
            }
        )

        # Redirect to frontend success page
        return RedirectResponse(f"{os.getenv("DOMAIN")}/hubspot-leads")

    except Exception as e:
        raise HTTPException(500, f"OAuth callback failed: {str(e)}")


# 4. Refresh token helper
async def refresh_hubspot_token(creds: HubSpotCRM) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                "client_id": HUBSPOT_CLIENT_ID,
                "client_secret": HUBSPOT_CLIENT_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()
        data = resp.json()

    creds.access_token = data["access_token"]
    creds.refresh_token = data["refresh_token"]
    creds.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
    await creds.save()

    return creds.access_token


# 5. Fetch leads (contacts in HubSpot) with auto-refresh
@hubspot_router.get("/fetch-hubspot-leads")
async def fetch_hubspot_leads(current_user: Annotated[User, Depends(get_current_user)]):
    creds = await HubSpotCRM.get_or_none(user=current_user)
    if not creds or not creds.access_token:
        raise HTTPException(404, "HubSpot CRM not connected.")

    # Check if expired → refresh
    if creds.expires_at and creds.expires_at < datetime.now(timezone.utc):
        try:
            access_token = await refresh_hubspot_token(creds)
        except Exception as e:
            raise HTTPException(401, f"Token refresh failed: {e}")
    else:
        access_token = creds.access_token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Fetch contacts (leads) - up to 40, with properties: lastname, phone, email
    params = {
        "limit": 40,
        "properties": "lastname,phone,email"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts", headers=headers, params=params)

        if resp.status_code == 401:
            # Force refresh and retry
            access_token = await refresh_hubspot_token(creds)
            headers["Authorization"] = f"Bearer {access_token}"
            resp = await client.get(f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts", headers=headers, params=params)

        if resp.status_code != 200:
            raise HTTPException(resp.status_code, "Failed to fetch leads from HubSpot")

    data = resp.json().get("results", [])
    # File & Lead saving (same as your Zoho/Close style)
    file = await File.get_or_none(user=current_user, type="hubspot") or await File.create(
        name="HubSpot Leads",
        type="hubspot",
        user=current_user
    )

    for contact in data:
        properties = contact.get("properties", {})
        phone = properties.get("phone")
        if not phone:
            continue

        if await Lead.filter(mobile=phone).exists():
            continue
        last_name = properties.get("lastname") or properties.get("firstname") or ""
        await Lead.create(
            first_name="",  # HubSpot has no separate first_name; use lastname or adjust
            last_name=last_name,
            email=properties.get("email", ""),
            mobile=phone,
            state=None,
            timezone=None,
            other_data=contact,
            file=file
        )

    all_leads = await Lead.filter(file=file).all()
    return {"leads": all_leads, "message": "Leads fetched and stored successfully"}