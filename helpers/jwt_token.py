import jwt
import os
from fastapi.security import  HTTPBearer,HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
from typing import Annotated
from models.user import User
security = HTTPBearer()


def generate_user_token(payload: dict):
    jwt_key = os.getenv("JWT_SECRET")
    token = jwt.encode(payload, jwt_key, algorithm='HS256')
    return token

def decode_user_token(token: str):
    print("token,", token)
    jwt_key = os.getenv("JWT_SECRET")
    return jwt.decode(token, jwt_key, algorithms=['HS256'])
 
async def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    token = credentials.credentials
    user_credential = decode_user_token(token=token)
    if user_credential:
        user = await User.filter(id=user_credential["id"]).first()
        if user:
            return user
        else:
            raise HTTPException(status_code=401, detail="Invalid Credentials")


async def get_active_user(user: Annotated[User, Depends(get_current_user)]):
    """
    Dependency that ensures the current user account is active.
    Raises 403 if user.is_active is False.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account is inactive. Please contact support."
        )
    return user


async def get_admin(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload =decode_user_token(token)
        user_id = payload["id"]
    except:
        raise credentials_exception
    
    if user_id is None:
        raise credentials_exception
    
    try:
        user = await User.filter(id=user_id).first()
        if not user.email_verified:
            raise credentials_exception
        if user.type.value != "admin":
            raise credentials_exception
        return user
    except:
        raise credentials_exception
    