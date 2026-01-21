import asyncio
import os
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends,HTTPException
import httpx
from helpers.jwt_token import get_admin, get_current_user
from helpers.vapi_helper import generate_token, get_headers
from models.call_log import CallLog
from models.lead import Lead
from models.zoho_crm import ZohoCRM
from pydantic import BaseModel
from models.user import User
from datetime import datetime
from tortoise.expressions import Q
from datetime import datetime
from models.file import File
from typing import Optional
import httpx
import requests
import os

crm_router = APIRouter()



class ZohoPayload(BaseModel):
    client_id: str
    client_secret:str
    code:str
        



@crm_router.get("/zoho-available")
async def zoho_available(current_user: Annotated[User, Depends(get_current_user)]):
    zoho_credentials = await ZohoCRM.get_or_none(user=current_user)
    if zoho_credentials:
        return{
            "success": True,
            "message": "Zoho CRM is connected."
        }
    else:
        return {
            "success": False,
            "message": "Zoho CRM is not connected."
        }

@crm_router.post("/add-zoho")
async def get_leads(current_user: Annotated[User, Depends(get_current_user)],
                    payload: ZohoPayload):
    try:
        
        ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
        req_body = {
        "client_id": payload.client_id,
        "client_secret": payload.client_secret,
        "grant_type": "authorization_code",
        "code": payload.code,
        }

        timeout = httpx.Timeout(10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(ZOHO_TOKEN_URL, data=req_body)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to to authenticate with Zoho CRM")
            response.raise_for_status()
            result = response.json()  
            if result.get("error"):
                return{
                    "success": False,
                    "detail":f"Error in Zoho CRM authentication: {result.get('error')}"
                }       
        
        await ZohoCRM.create(
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            code=payload.code,
            access_token=result.get("access_token"),
            refresh_token=result.get("refresh_token"),
            api_domain=result.get("api_domain"),
            user=current_user
        )

        return {
            "success": True,
            "detail": "Zoho CRM credentials added successfully."
        }
    except Exception as e:
         raise HTTPException(status_code=500, detail="Failed to add Zoho CRM credentials.")


@crm_router.get("/fetch-zoho-leads")
async def fetch_zoho_leads(current_user: Annotated[User, Depends(get_current_user)]):
    try:
        zoho_credentials = await ZohoCRM.get_or_none(user=current_user)
        if not zoho_credentials:
            raise HTTPException(status_code=404, detail="Zoho CRM credentials not found for the user.")

        ZOHO_LEADS_URL = f"{zoho_credentials.api_domain}/crm/v8/Leads"
        headers = {
            "Authorization": f"Zoho-oauthtoken {zoho_credentials.access_token}"
        }
        params = {
            "fields": "Last_Name,Phone,Email,Record_Status__s,Converted__s,Converted_Date_Time",
            "converted": "true",
            "per_page": 40
        }

        timeout = httpx.Timeout(10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(ZOHO_LEADS_URL, headers=headers, params=params)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch leads from Zoho CRM")

        data = response.json().get("data", [])
        # return data
        # ---------- FILE HANDLING ----------

        file = await File.get_or_none(user=current_user, type="zoho")

        if not file:
            file = await File.create(
                name="Zoho Leads",
                type="zoho",
                user=current_user
            )

        # ---------- SAVE LEADS ----------
        for lead in data:
            phone = lead.get("Phone")


            # skip if phone missing
            if not phone:
                continue
      

            # check duplicate by phone
            exists = await Lead.filter(mobile=phone).exists()
            if exists:
                continue

            await Lead.create(
                first_name="",
                last_name=lead.get("Last_Name", ""),
                email=lead.get("Email", ""),
                mobile=phone,
                state=None,
                timezone=None,
                other_data=lead,
                file=file
            )
        print("90-090-09")
        all_leads = await Lead.filter(file=file).all()
        return {"leads": all_leads , "message": "Leads fetched and stored successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch leads from Zoho CRM. {e}")



@crm_router.get("/generate-zoho-access-token")
async def generate_zoho_access_token(current_user: Annotated[User, Depends(get_current_user)]) -> str:
    zoho_credentials = await ZohoCRM.get_or_none(user=current_user)
    if not zoho_credentials:
        raise HTTPException(status_code=404, detail="Zoho CRM credentials not found for the user.")
    try:
        ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
        req_body = {
            "client_id": zoho_credentials.client_id,
            "client_secret": zoho_credentials.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": zoho_credentials.refresh_token,
        }

        timeout = httpx.Timeout(10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(ZOHO_TOKEN_URL, data=req_body)
            response.raise_for_status()
            result = response.json()  
            new_access_token = result.get("access_token")
            zoho_credentials.access_token = new_access_token
            await zoho_credentials.save()

            return {"access_token": new_access_token}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate Zoho CRM access token.")
    
    
    
    
    
    