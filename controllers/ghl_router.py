from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from models.user_keys import  UserKeys
from models.user import User

from pydantic import BaseModel, Field
from typing import Optional
from helpers.jwt_token import get_current_user
class GHLSettingBase(BaseModel):
    ghl_key: str = Field(..., min_length=10, description="GHL API Key")

class GHLSettingCreate(GHLSettingBase):
    pass

class GHLSettingUpdate(BaseModel):
    ghl_key: Optional[str] = Field(None, min_length=10, description="GHL API Key")

ghl_router = APIRouter(prefix="/ghl")

# POST - Create or Update GHL Setting
@ghl_router.post("/settings")
async def create_or_update_ghl_setting(
    setting_data: GHLSettingCreate,
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Create or update GHL API key for the current user.
    If setting exists, it will be updated.
    """
    user = current
    
    # Check if user key already exists
    existing_keys = await UserKeys.get_or_none(user=user)
    
    if existing_keys:
        # Update existing GHL key
        existing_keys.ghl_key = setting_data.ghl_key
        await existing_keys.save()
        return existing_keys
    
    # Create new user key
    new_keys = await UserKeys.create(
        user=user,
        ghl_key=setting_data.ghl_key
    )
    
    return new_keys

# GET - Get GHL Setting
@ghl_router.get("/ghl_setting")
async def get_ghl_setting(
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Get GHL API key for the current user.
    """
    user = current
    
    user_keys = await UserKeys.get_or_none(user=user)
    
    if not user_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GHL API key not found. Please create it first."
        )
    
    return user_keys

@ghl_router.put("/ghl_settings")
async def update_ghl_setting(
    setting_data: GHLSettingUpdate,
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Update GHL API key for the current user.
    """
    user = current
    
    user_keys = await UserKeys.get_or_none(user=user)
    
    if not user_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GHL API key not found. Please create it first using POST."
        )
    
    if setting_data.ghl_key:
        user_keys.ghl_key = setting_data.ghl_key
        await user_keys.save()
    
    return user_keys

# PATCH - Partially update GHL Setting
@ghl_router.patch("/settings")
async def patch_ghl_setting(
    setting_data: GHLSettingUpdate,
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Update GHL API key for the current user.
    """
    user = current
    
    user_keys = await UserKeys.get_or_none(user=user)
    
    if not user_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GHL API key not found. Please create it first."
        )
    
    if setting_data.ghl_key:
        user_keys.ghl_key = setting_data.ghl_key
        await user_keys.save()
    
    return user_keys

# DELETE - Delete GHL Setting
@ghl_router.delete("/settings")
async def delete_ghl_setting(
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Delete GHL API key for the current user.
    """
    user = current
    
    user_keys = await UserKeys.get_or_none(user=user)
    
    if not user_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GHL API key not found."
        )
    
    await user_keys.delete()
    
    return {
        "message": "GHL API key deleted successfully",
        "deleted": True
    }

# GET - Check if GHL Setting exists
@ghl_router.get("/settings/check")
async def check_ghl_setting(
    current: Annotated[User, Depends(get_current_user)]
):
    """
    Check if GHL API key exists for the current user.
    """
    user = current
    
    user_keys = await UserKeys.get_or_none(user=user)
    
    return {
        "exists": user_keys is not None,
        "has_ghl_key": bool(user_keys and user_keys.ghl_key) if user_keys else False
    }