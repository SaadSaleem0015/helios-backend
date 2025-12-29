from typing import Annotated, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from helpers.jwt_token import get_admin
from models.defaultSettings import DefaultSettings
from models.user import User

default_settings_router = APIRouter()

class SettingsData(BaseModel):
    max_duration: Optional[int] = None
    phone_number_price: Optional[float] = None
    warm_transfer_fee: Optional[float] = None
    seconds_per_dollar: Optional[float] = None
    monthly_fee: Optional[int] = None
    max_calls: Optional[int] = None
    call_frequency: Optional[int] = None
    call_period_minutes: Optional[int] = None
    max_call_limit_free_trial: Optional[int] = None
    max_lead_limit_free_trial: Optional[int] = None

@default_settings_router.put("/default_settings")
async def update_settings(
    settings: SettingsData, 
    user: Annotated[User, Depends(get_admin)]
):
    default_setting = await DefaultSettings.first()
    
    if not default_setting:
        default_setting = await DefaultSettings.create(
            max_call_duration=settings.max_duration,
            phone_number_price=settings.phone_number_price,
            transfer_rate=settings.warm_transfer_fee,
            seconds_per_dollar=settings.seconds_per_dollar,
            monthly_fee=settings.monthly_fee,
            max_calls=settings.max_calls,
            call_frequency=settings.call_frequency or 10,
            call_period_minutes=settings.call_period_minutes or 3,
            max_call_limit_free_trial=settings.max_call_limit_free_trial or 2000,
            max_lead_limit_free_trial=settings.max_lead_limit_free_trial or 3000,
        )
    else:
        # Update only provided fields
        if settings.max_duration is not None:
            default_setting.max_call_duration = settings.max_duration
        if settings.phone_number_price is not None:
            default_setting.phone_number_price = settings.phone_number_price
        if settings.warm_transfer_fee is not None:
            default_setting.transfer_rate = settings.warm_transfer_fee
        if settings.seconds_per_dollar is not None:
            default_setting.seconds_per_dollar = settings.seconds_per_dollar
        if settings.monthly_fee is not None:
            default_setting.monthly_fee = settings.monthly_fee
        if settings.max_calls is not None:
            default_setting.max_calls = settings.max_calls
        if settings.call_frequency is not None:
            default_setting.call_frequency = settings.call_frequency
        if settings.call_period_minutes is not None:
            default_setting.call_period_minutes = settings.call_period_minutes
        if settings.max_call_limit_free_trial is not None:
            default_setting.max_call_limit_free_trial = settings.max_call_limit_free_trial
        if settings.max_lead_limit_free_trial is not None:
            default_setting.max_lead_limit_free_trial = settings.max_lead_limit_free_trial
        
        await default_setting.save()
    
    return {"success": True, "detail": "Default settings updated successfully"}

@default_settings_router.get("/get-default-settings")
async def get_settings(
    user: Annotated[User, Depends(get_admin)]
):
    default_setting = await DefaultSettings.first()
    
    if not default_setting:
        # Return default values if no settings exist
        return {
            "id": None,
            "max_call_duration": None,
            "max_calls": None,
            "transfer_rate": None,
            "monthly_fee": None,
            "phone_number_price": None,
            "seconds_per_dollar": None,
            "call_frequency": 10,
            "call_period_minutes": 3,
            "max_call_limit_free_trial": 2000,
            "max_lead_limit_free_trial": 3000
        }
    
    return default_setting