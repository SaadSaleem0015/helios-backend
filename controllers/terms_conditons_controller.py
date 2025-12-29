from fastapi import APIRouter
from pydantic import BaseModel
import dotenv
from helpers.jwt_token import get_current_user
from models.purchased_number import PurchasedNumber
from models.termsandconditions import TermsAndConditions

dotenv.load_dotenv()
terms_router = APIRouter()

class TermsAndConditionsSchema(BaseModel):
    content: str

@terms_router.get("/get-terms-and-conditions")
async def get_terms():
    terms = await TermsAndConditions.first()
    if not terms:
        return {"content": ""}
    return terms

@terms_router.post("/terms-and-conditions")
async def update_terms(terms_data: TermsAndConditionsSchema):
    terms = await TermsAndConditions.first()
    if terms:
        terms.content = terms_data.content
        await terms.save()
        return {"success" : True, "detail" : "Updated Successfully"}
    else:
        terms = await TermsAndConditions.create(content=terms_data.content)
    return {"success" : True, "detail" : "Added Successfully"}
   