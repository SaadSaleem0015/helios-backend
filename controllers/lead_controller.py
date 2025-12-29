from fastapi import APIRouter, Form, UploadFile, File as FastAPIFile, HTTPException, Depends
# from helpers.criteria_check import has_payment_method
from helpers.jwt_token import get_admin
from helpers.import_leads_csv import import_leads_csv, humanize_results
from helpers.state import stateandtimezone
from models.lead import Lead
from models.user import User
from models.file import File as FileModel
from pydantic import BaseModel
from typing import List, Annotated, Optional
from httpx import AsyncClient
import asyncio
# from config import scheduler_status
from datetime import datetime, timedelta
from typing import Annotated, Optional, Dict
from pydantic import BaseModel, EmailStr, StringConstraints
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict
from pydantic import StringConstraints
from typing_extensions import Annotated
# from models.vv_adminSetting import VVadminSetting
from helpers.jwt_token import get_current_user
leads_router = APIRouter()

class DeleteLeadPayload(BaseModel):
    ids: List[int]
class StateUpdateRequest(BaseModel):
    state: str

class CreateLeadPayload(BaseModel):
    first_name: str
    last_name: str
    email: str
    add_date: str  
    mobile: str
    file_id: Optional[int]
    salesforce_id: str 
    other_data:List[str] 






class LeadInput(BaseModel):
    api_key: str
    first_name: str
    last_name: str
    email: EmailStr
    mobile: Annotated[str, StringConstraints(min_length=10, max_length=10, pattern=r'^\d{10}$')]  
    file_id: Optional[Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9\-]{8,}$')]] = None 

    @validator('file_id', always=True)
    def check_file_id(cls, v):
        if v and len(v) != 8:
            raise ValueError('Invalid file ID: it must be exactly 8 digits.')
        return v

    lead_id: Optional[str] = None
    other_data: Optional[Dict] = None



        
@leads_router.post("/add_manually_lead")
async def add_lead_manually( data: CreateLeadPayload, user: Annotated[User, Depends(get_current_user)]):
    try:
        # payment_method = await has_payment_method(main_admin)
        # if not payment_method:
        #    return {
        #         "success":False,
        #         "detail": f"Unable to add lead. You should have an active payment method first.",
        #     }
        if data.file_id:
            file = await FileModel.filter(id=data.file_id).first()
            if not file:
                raise HTTPException(status_code=404, detail="File not found")
            
        lead = await Lead.create(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            add_date=data.add_date,
            mobile=data.mobile,
            file_id=data.file_id,
            other_data=data.other_data
        )
        await lead.save()
        return {"success": True, "detail": "Lead added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
@leads_router.put("/update-lead-state/{leadId}")
async def add_lead_manually( leadId: int, data:StateUpdateRequest , user: Annotated[User, Depends(get_current_user)]):
    try:
        states = stateandtimezone()
        time_zones = {entry["name"] : entry['zone'] for entry in states}
        state = data.state.strip().lower()

        matching_state = next((state_name for state_name in time_zones if state in state_name.lower()), None)
        lead = await Lead.filter(id = leadId).first()
        if matching_state:
           timezone = time_zones[matching_state]
           lead.timezone = timezone
           lead.state = data.state
           await lead.save()
           return {"success": True, "detail": "Lead updated successfully"}
        else:
           timezone = None
           lead.timezone = timezone
           await lead.save()
           return {"success": False, "detail": "Unable to update lead. State is not correct"}
           

        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
  

def is_within_trial_period(user_free_trial_start: datetime, has_free_trial: bool) -> bool:
    if user_free_trial_start is None:
        print("trial is not started yet but can upload leads to complete the profile")
        return True
    
    print("trial started and check the and process to lead upload if with the trial")
    user_free_trial_start = user_free_trial_start.replace(tzinfo=None)
    trial_end_date = user_free_trial_start + timedelta(weeks=2)
    current_time = datetime.now().replace(tzinfo=None)  
    return has_free_trial and current_time < trial_end_date

def count_leads_in_csv(content: str) -> int:
    rows = [row for row in content.splitlines() if row.strip() != '']
    return len(rows) - 1 if len(rows) > 0 else 0

async def process_file_upload(content: str, file: UploadFile, name: str, user: User, trial_leads=None, message=None):
    try:
  
        file_record = FileModel(name=name, user=user)
        await file_record.save()

        results = await import_leads_csv(content, file_record)

        return { 
            "success": True,
            "results": results,
            "detail": humanize_results(results),
            "message": message
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

async def get_lead_count_for_user(user_id: int) -> int:
    try:
        files = await FileModel.filter(user_id=user_id).all()

        file_ids = [file.id for file in files]

        if file_ids:
            leads = await Lead.filter(file_id__in=file_ids).all()
            
            return len(leads)
        else:
            return 0
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving leads: {str(e)}")

@leads_router.post("/files")
async def import_leads_file(user: Annotated[User, Depends(get_current_user)], 
                             file: UploadFile = FastAPIFile(...), name: str = Form(...)):
    try:  
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8")
        
        

        if file.filename.split(".")[-1] != "csv":
            raise HTTPException(
                status_code=400,
                detail="Unsupported Format. Only CSV files are allowed."
            )

        # if user.has_active_subscription:
        #     payment_method = await has_payment_method(user)
        #     if payment_method:
        #         return await process_file_upload(content, file, name, user)
        #     else:
        #         raise HTTPException(
        #             status_code=400,
        #             detail="Don't have active payment method."
        #         )

        # if is_within_trial_period(user.free_trial_start, user.has_free_trial):
        num_leads = count_leads_in_csv(content)
                 
        total_leads = await get_lead_count_for_user(user.id)
            
            # setting = await VVadminSetting.filter(user_id=user.id).first()
            # max_lead_limit = setting.max_lead_limit_free_trial if setting and setting.max_lead_limit_free_trial is not None else 1000
            
        max_lead_limit = 30
        print(f"The max lead limt for this user is {max_lead_limit}")
            
        if total_leads > max_lead_limit:
                return {
                    "success":False,
                    "detail":f"Only {max_lead_limit} leads allow to upload in Free Version"
                }
                            
        if num_leads > max_lead_limit:
                content = "\n".join(content.splitlines()[:max_lead_limit])
                message = f"Only {max_lead_limit} leads will be uploaded due to free Version restrictions."

                return await process_file_upload(content, file, name, user, num_leads, message)

        return await process_file_upload(content, file, name, user, num_leads,None)

        # raise HTTPException(
        #     status_code=400,
        #     detail="Your free trial has expired. Please purchase a subscription to continue uploading leads."
        # )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@leads_router.get("/files")
async def get_files(user: Annotated[User, Depends(get_current_user)]):
    files = await FileModel.filter(user=user).all().order_by("-id")
    files_with_leads_count = []
    for file in files:
        leads_count = await Lead.filter(file=file).count()
        files_with_leads_count.append({
            "id":file.id,
            "name":file.name,
            "alphanumeric_id":file.alphanumeric_id,
            "created_at":file.created_at,
            "leads_count": leads_count
        })                                                                    
    return files_with_leads_count


@leads_router.delete("/files/{id}")
async def delete_file(id: int,user: Annotated[User, Depends(get_current_user)]):
    file = await FileModel.get_or_none(id=id)
  
    await file.delete()
    return { "success": True, "detail": "File deleted successfully." }


@leads_router.get("/admin_leads/{file_id}")
async def leads(user: Annotated[User, Depends(get_current_user)],file_id: Optional[int] = None, user_id: Optional[int] = None,): 
    try:
        filters = {}
        if file_id:
            filters["file_id"] = file_id
        if user_id:
            filters["file__user_id"] = user_id
        leads = await Lead.filter(**filters).all()
        file = await FileModel.filter(id=file_id).first()
        if not file:
            return[]
        return leads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@leads_router.get("/leads")
async def leads(user: Annotated[User, Depends(get_current_user)], file_id: Optional[int] = None):
    print("lllll")

    filters = { "file__user_id": user.id , "dnc" : False }
    if file_id:
        filters["file_id"] = file_id
    return await Lead.filter(**filters).all().order_by("id")

@leads_router.get("/leads/{lead_id}")
async def leads(user: Annotated[User, Depends(get_current_user)], lead_id:int):
    print("lead_id",)
    filters = { "file__user_id": user.id ,"dnc" : False }
    if lead_id:
        filters["id"] = lead_id
    return await Lead.filter(**filters)

@leads_router.get("/admin/leads")
async def leads(user: Annotated[User, Depends(get_current_user)],file_id: Optional[int] = None, user_id: Optional[int] = None): 
    filters = { "file__user_id": user_id }
    if file_id:
        filters["file_id"] = file_id
    return await Lead.filter(**filters).all()

@leads_router.delete("/leads")
async def delete_lead(data: DeleteLeadPayload, user: Annotated[User, Depends(get_current_user)]):
    leads = await Lead.filter(id__in=data.ids, file__user_id=user.id).all()
    await asyncio.gather(*[lead.delete() for lead in leads])
    return { 
        "success": True, 
        "detail": "Lead(s) deleted successfully." 
    }

@leads_router.get("/all_leads/all_files")
async def get_files(user: Annotated[User, Depends(get_admin)]):
    files = await FileModel.all().prefetch_related("user").order_by("id")
    return [{
        **dict(file),
        "user": file.user,
    } for file in files]



@leads_router.get("/all_leads/all_files/{user_id}")
async def get_files_by_company(user_id: int, user: Annotated[User, Depends(get_admin)]):
    try:
        files = await FileModel.filter(user__id=user_id).prefetch_related("user").order_by("id")
        
        if not files:
            raise HTTPException(status_code=404, detail="No files found")
        
        return [{
            **dict(file),
            "user": file.user,
        } for file in files]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


