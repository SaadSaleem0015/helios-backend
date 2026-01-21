from fastapi import APIRouter, Depends, HTTPException, Request
import pytz
from controllers.call_controller import analyze_dnc
from helpers.jwt_token import get_current_user, get_admin
from helpers.email import send_dnc_email
from helpers.state import stateandtimezone
from models.dnc import Dnc
from models.lead import Lead
from models.purchased_number import PurchasedNumber
from models.user import User
from typing import Annotated, List
from pydantic import BaseModel

dnc_router = APIRouter()


class DncPromptCreate(BaseModel):
    prompt: str


class DncPromptUpdate(BaseModel):
    prompt: str


class DncPromptResponse(BaseModel):
    prompt: str


@dnc_router.post("/dnc")
async def create_dnc_prompt(
    data: DncPromptCreate, user: Annotated[User, Depends(get_admin)]
):
    await Dnc.create(prompt=data.prompt)
    return {"success": True,  "detail": "DNC Prompt has been added successfully"}


@dnc_router.delete("/delete-dnc-prompt/{id}")
async def delete_dnc_prompt(id: int, user: Annotated[User, Depends(get_admin)]):
    dnc = await Dnc.filter(id=id).first()
    if not dnc:
        raise HTTPException(status_code=404, detail="DNC prompt not found")
    await dnc.delete()
    return {"success": True,  "detail": "DNC prompt deleted successfully"}



@dnc_router.put("/update-dnc-prompt/{id}")
async def update_dnc_prompt(
    id: int, data: DncPromptUpdate, user: Annotated[User, Depends(get_admin)]
):
    dnc = await Dnc.filter(id=id).first()
    if not dnc:
        raise HTTPException(status_code=404, detail="DNC prompt not found")
    dnc.prompt = data.prompt
    await dnc.save()
    return {"success": True,  "detail": "DNC Prompt has been updated successfully"}


@dnc_router.get("/all-dnc-prompts")
async def get_all_dnc_prompts(user: Annotated[User, Depends(get_admin)]):
    dnc = await Dnc.all()
    return dnc

@dnc_router.get("/dnc-leads")
async def dnc_leads(user: Annotated[User, Depends(get_current_user)]):
   leads = await Lead.filter(dnc = True , file__user_id = user.id).all().order_by("id")
   return leads

@dnc_router.get("/company-dnc-leads/{companyId}")
async def dnc_leads(companyId: int, user: Annotated[User, Depends(get_admin)]):
   leads = await Lead.filter(dnc = True , file__user_id = companyId).all().order_by("id")
   return leads
@dnc_router.get("/requested-leads")
async def dnc_leads(user: Annotated[User, Depends(get_current_user)]):
   leads = await Lead.filter(submit_for_approval = True , dnc = False, file__user_id = user.id).all().order_by("id")
   return leads
 
@dnc_router.post("/add-lead-todnc/{leadId}")
async def add_lead_to_dnc(leadId : int , user:Annotated[User, Depends(get_current_user)]):
    try:
        lead = await Lead.filter(id = leadId).first()
        message = ''
        if user.role == 'company_admin' :
            lead.dnc = True
            message = "Lead is added to DNC"
            await lead.save(update_fields=["dnc"])
        else:
            lead.submit_for_approval = True
            message = "Your request to make this lead DNC has been sent to the admin"
            await lead.save(update_fields=["submit_for_approval"])
        return {"success":True, "detail" : message}
    except Exception as e:
        print("Error:", str(e)) 
        raise HTTPException(status_code=400, detail=f"{str(e)}")

@dnc_router.post("/approve-dnc/{leadId}")
async def add_lead_to_dnc(leadId : int , user:Annotated[User, Depends(get_current_user)]):
    try:
        lead = await Lead.filter(id = leadId).first()
        lead.dnc = True
        lead.submit_for_approval = False
        await lead.save(update_fields=["dnc" , "submit_for_approval"])
        return {"success":True, "detail" : "Lead added to DNC"}
    except Exception as e:
        print("Error:", str(e)) 
        raise HTTPException(status_code=400, detail=f"{str(e)}")



@dnc_router.post("/sms")
async def sms(request: Request):
    form_data = await request.form()
    body = form_data.get('Body')
    from_number = form_data.get('From')
    prompts = await Dnc.all()
    to_number = form_data.get('To') 
    numberowner = await PurchasedNumber(phone_number = to_number).first()
    lead = await Lead.filter(mobile=from_number , file__user_id = numberowner.user_id).first()
    if not lead:
        normalized_from_number = from_number.lstrip('+1') if from_number.startswith('+1') else from_number
        lead = await Lead.filter(mobile=normalized_from_number,file__user_id = numberowner.user_id).first()
    if not lead:
        return {'success' : True , 'Detail' : 'phone number is not lead'}
         
    is_dnc = await analyze_dnc(body ,prompts)
    if is_dnc:
               send_dnc_email(user.email, lead.email, lead.first_name, lead.last_name)
               lead.dnc = is_dnc
               print("Dnc message recieved")
               await lead.save(update_fields=['dnc'])

    return {'success' : True , 'Detail' : 'Message recived'}


@dnc_router.get("/states")
async def states(user: Annotated[User, Depends(get_current_user)]):
 
   return stateandtimezone()


