import asyncio
import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
import httpx
from helpers.jwt_token import get_current_user
from models.close_crm import CloseCRM
from models.lead import Lead
from models.user import User
from models.file import File
from pydantic import BaseModel
from datetime import datetime, timedelta
import urllib.parse

crm_router = APIRouter()

# ── Constants ────────────────────────────────────────────────────────────────
CLOSE_AUTH_URL = "https://app.close.com/oauth2/authorize/"
CLOSE_TOKEN_URL = "https://api.close.com/oauth2/token/"
CLOSE_REVOKE_URL = "https://api.close.com/oauth2/revoke/"
CLOSE_API_BASE = "https://api.close.com/api/v1/"

# Replace with YOUR registered redirect URI
REDIRECT_URI = "https://bee584f6f9fc.ngrok-free.app/api/crm/callback/close"  # MUST match what you set in Close OAuth App


class CloseConnectRequest(BaseModel):
    client_id: str
    client_secret: str


# 1. Check if connected
@crm_router.get("/close-available")
async def close_available(current_user: Annotated[User, Depends(get_current_user)]):
    creds = await CloseCRM.get_or_none(user=current_user)
    return {
        "success": bool(creds and creds.access_token),
        "message": "Close CRM is connected." if creds else "Close CRM is not connected."
    }


# 2. Start OAuth flow - User provides client_id/secret once (or you can hardcode them if single app)
#    In multi-tenant, you might store global client_id/secret and skip this
@crm_router.post("/connect-close")
async def connect_close(
    payload: CloseConnectRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    # Optional: validate by storing temporarily or just redirect immediately
    # For simplicity, we store them and initiate redirect

    # Build authorize URL
    params = {
        "client_id": payload.client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        # "scope": "all.full_access offline_access",  # usually auto-granted by Close
        "state": current_user.id  # Optional: anti-CSRF, pass user id
    }

    auth_url = f"{CLOSE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    return {
        "success": True,
        "authorize_url": auth_url,
        "message": "Redirect user to this URL to connect Close CRM"
    }


# 3. Callback - Close redirects here with code
@crm_router.get("/callback/close")
async def close_oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None)
):
    # In production: validate state matches user/session
    # Here we assume simple flow

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                CLOSE_TOKEN_URL,
                data={
                    "client_id": "YOUR_CLIENT_ID_HERE",       # ← Replace or fetch from DB/global
                    "client_secret": "YOUR_CLIENT_SECRET_HERE",  # ← Replace or fetch
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            resp.raise_for_status()
            tokens = resp.json()

        # Find user (from state or session)
        # For demo: assume you get user from auth or pass via state
        user_id = int(state) if state else None  # ← Improve this!
        user = await User.get_or_none(id=user_id)
        if not user:
            raise HTTPException(400, "Invalid state/user")

        await CloseCRM.update_or_create(
            user=user,
            defaults={
                "client_id": "YOUR_CLIENT_ID_HERE",  # or payload value
                "client_secret": "YOUR_CLIENT_SECRET_HERE",
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": datetime.utcnow() + timedelta(seconds=tokens["expires_in"]),
                "organization_id": tokens.get("organization_id"),
                "close_user_id": tokens.get("user_id")
            }
        )

        # Redirect to frontend success page
        return RedirectResponse("https://yourapp.com/integrations?success=close")

    except Exception as e:
        raise HTTPException(500, f"OAuth callback failed: {str(e)}")


# 4. Refresh token helper (call when 401 or before fetch)
async def refresh_close_token(creds: CloseCRM) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            CLOSE_TOKEN_URL,
            data={
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token
            }
        )
        resp.raise_for_status()
        data = resp.json()

    creds.access_token = data["access_token"]
    creds.refresh_token = data.get("refresh_token", creds.refresh_token)  # Close issues new refresh
    creds.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
    await creds.save()

    return creds.access_token


# 5. Fetch leads (with auto-refresh)
@crm_router.get("/fetch-close-leads")
async def fetch_close_leads(current_user: Annotated[User, Depends(get_current_user)]):
    creds = await CloseCRM.get_or_none(user=current_user)
    if not creds or not creds.access_token:
        raise HTTPException(404, "Close CRM not connected.")

    # Check if expired → refresh
    if creds.expires_at and creds.expires_at < datetime.utcnow():
        try:
            access_token = await refresh_close_token(creds)
        except Exception as e:
            raise HTTPException(401, f"Token refresh failed: {e}")
    else:
        access_token = creds.access_token

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    params = {
        "_fields": "display_name,contacts,status_label",
        "_limit": 40
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{CLOSE_API_BASE}lead/", headers=headers, params=params)

        if resp.status_code == 401:
            # Force refresh and retry once
            access_token = await refresh_close_token(creds)
            headers["Authorization"] = f"Bearer {access_token}"
            resp = await client.get(f"{CLOSE_API_BASE}lead/", headers=headers, params=params)

        if resp.status_code != 200:
            raise HTTPException(resp.status_code, "Failed to fetch leads from Close")

    data = resp.json().get("data", [])

    # File & Lead saving (same as your Zoho style)
    file = await File.get_or_none(user=current_user, type="close") or await File.create(
        name="Close Leads",
        type="close",
        user=current_user
    )

    for lead in data:
        for contact in lead.get("contacts", []):
            phone = next((p["phone"] for p in contact.get("phones", []) if p.get("phone")), None)
            if not phone:
                continue

            if await Lead.filter(mobile=phone).exists():
                continue

            await Lead.create(
                first_name="",
                last_name=contact.get("name", lead.get("display_name", "")),
                email=contact.get("emails", [{}])[0].get("email", ""),
                mobile=phone,
                state=None,
                timezone=None,
                other_data=lead,
                file=file
            )

    all_leads = await Lead.filter(file=file).all()
    return {"leads": all_leads, "message": "Leads fetched and stored successfully"}