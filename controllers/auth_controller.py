import datetime
from fastapi import APIRouter, HTTPException, Depends
from argon2 import PasswordHasher
from pydantic import BaseModel, EmailStr
from typing import Annotated,Optional
from models.user import User
from models.code import Code
from helpers.jwt_token import generate_user_token, get_admin, get_current_user
from helpers.email import generate_code
import pytz



auth_router = APIRouter()
ph = PasswordHasher()


class SignupPayload(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginPayload(BaseModel):
    email: EmailStr
    password: str

class AccountVerificationPayload(BaseModel):
    email: EmailStr
    code: int

class PasswordResetCode(BaseModel):
    email: EmailStr

class VerifyCodePayload(BaseModel):
    email: EmailStr
    code: str
    
class ResetCodePayload(BaseModel):
    email: EmailStr
    code: str
    password: str
    
class UpdateProfilePayload(BaseModel):
    email: EmailStr
    name: str
    newPassword: Optional[str] = None
    currentPassword:Optional[str] = None
    
    

class UpdateAdminProfilePayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None



class AccessChangePayload(BaseModel):
    name:str
    password:str

@auth_router.post('/signup')
async def  signup(payload: SignupPayload):
    user = await User.filter(email = payload.email).first()
    if user: 
        raise HTTPException(status_code=400, detail="User already exists")
    try:
        user = User(
            name = payload.name,
            email = payload.email,
            password = ph.hash(payload.password),
        )
        await user.save()

        is_email_sent:bool = await generate_code("account_activation", user=user)
        if(is_email_sent):
            return {
                "success": True, 
                "verify": True,
                "detail": "Verification Email send successfully" ,
            
        }
        else:
            await user.delete()

            return {"success": True, "message": "Verification email not sent"}
    except Exception as e:
        raise HTTPException(status_code=400,detail=f"server error {e}")
    
@auth_router.post("/login")
async def signin(data: LoginPayload):
    user = await User.filter(email=data.email).first()
    if not user:
        raise HTTPException(
            status_code=400, 
            detail="User Not found"
        )
    print("----111")
    try:
        is_varified = ph.verify(user.password, data.password)
        print(f"IS Varified: {is_varified}")
    except:
        raise HTTPException(
            status_code=400, 
            detail="Invalid Credentials."
        )
    print("----")
    if user.email_verified == False:
        is_email_sent:bool = await generate_code("account_activation", user=user)
        if is_email_sent:
            return  {
                "success":True,
                "verify": False,
                "detail":"Email not verified verfication code sent successfully"
            }
        else:

            raise HTTPException(
                status_code=400,
                detail="Email not verified verfication code not sent")
    try:
        token = generate_user_token({ "id": user.id })
        return { 
            "success": True,
            "verified" : True,
            "token": token,
            "user": {
                'name': user.name,
                'email': user.email,
                'type':user.type,
            },
            "detail":"Login Successfully"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail= str(e)
        )

    

@auth_router.post("/activate")
async def account_verificatoin(payload: AccountVerificationPayload):
    user = await User.filter(email=payload.email).first()
    if not user:
        raise HTTPException(detail="User not found", status_code=400)
    print(f"Payload: {payload.code}")
    code = await Code.filter(user__id=user.id).order_by("-id").first()
    
    if not code:
        raise HTTPException(detail="Invalid code", status_code=400)
    try:
        if (code.value == str(payload.code)):
            user.email_verified = True
            await user.save()
            # confirmation_email(to_email=user.email)
            # await code.delete()
            token = generate_user_token({ "id": user.id })
            return {
                "success": True,
                "token": token,
                "user": {
                    'name': user.name,
                    "token": token,
                    'type':user.type,
                    'email': user.email,
                },
                "detail": "Account verified successfully"
            }
    except Exception as e:
        raise HTTPException(detail=f"Invalid code {str(e)}", status_code=400)



@auth_router.post("/resend-otp")
async def resend_otp(payload: PasswordResetCode):
    user = await User.filter(email=payload.email).first()
    if not user:
        raise HTTPException(detail="Account not found ", status_code=400)
    try:
        await generate_code("account_activation", user)
        return {
            "success": True,
            "detail": "Account activation code sent successfully"
        }
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500)
    
@auth_router.post("/send-reset-code")
async def password_reset_code(payload: PasswordResetCode):
    user = await User.filter(email=payload.email).first()
    if not user:
        raise HTTPException(detail="Account not found ", status_code=400)
    try:
        await generate_code("password_reset", user)
        return {
            "success": True,
            "detail": "Password reset code sent successfully"
        }
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500)




@auth_router.post("/confirm-otp")
async def confirm_otp(payload: VerifyCodePayload):
    user = await User.filter(email=payload.email).first()
    if not user:
        raise HTTPException(detail="User not found", status_code=400)
    if user:
        code  = await Code.filter(user__id=user.id, type="password_reset").order_by("-id").first()
        if not code:
            raise HTTPException(detail="Invalid Code", status_code=400)
        if payload.code == code.value:
            return {
                "success": True,
                "detail": "Otp verified successfully"
            }
        else:
            raise HTTPException(detail="Invalid code", status_code=400)
    else:
        raise HTTPException(detail="User not found", status_code=400)
    
    
@auth_router.post("/reset-password")
async def reset_password(payload: ResetCodePayload):
    try:
        user = await User.filter(email=payload.email).first()
        if user:
            code  = await Code.filter(user__id=user.id, type="password_reset").order_by("-id").first()
            if not code:
                raise HTTPException(detail="Code not found", status_code=400)
            if payload.code == code.value:
                hashed_password = ph.hash(payload.password)
                user.password = hashed_password
                await user.save()
                await code.delete()
                return {
                    "success": True,
                    "detail": "Password reset successfully"
                }
            else:
                raise HTTPException(detail="Invalid code", status_code=400)
        else:
            raise HTTPException(detail="User not found", status_code=400)
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=400)
    
@auth_router.get("/validate-token")
async def validate_token(user: Annotated[User, Depends(get_current_user)]):
 
    if user:
        return {
            "success": True,
            "detail": "Token verified successfully"
        } 

@auth_router.put("/update-profile")
async def update_profile(data: UpdateProfilePayload,user:Annotated[User,Depends(get_current_user)]):
    if await User.filter(email=data.email).first():
        if data.email != user.email:
            
            raise HTTPException(detail="Email already exists", status_code=400)
    if data.newPassword:
        try:
            ph.verify(user.password,data.currentPassword) # type: ignore
        except:
            raise HTTPException(status_code=403,detail="Current password is incorrect")
    try:
        if data.newPassword:
            hashed_password = ph.hash(data.newPassword)
            user.password = hashed_password
        user.name = data.name
        user.email = data.email
        await user.save()
        return {
            "success": True,
            "data": {
                "name": user.name,
                "email": user.email,
            },
            "detail": "Profile updated successfully"
        }
            
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=400)


@auth_router.get("/profile")
async def get_profile(user:Annotated[User,Depends(get_current_user)]):
    return {
      
            "name": user.name,
            "email": user.email,
            "type":user.type,
            "created_at":user.created_at,
    
    }



@auth_router.put("/admin_profile")
async def update_profile(data: UpdateAdminProfilePayload, user: User = Depends(get_admin)):

    existing_user = await User.filter(email = data.email).exclude(id=user.id).filter()
    if existing_user:
       raise HTTPException(status_code=403, detail="This user is already exists.")

    if data.name:
        user.name = data.name
    if data.email:
        user.email = data.email
    
    if data.password:
        user.password = ph.hash(data.password)
    await user.save()



    return {"success": True, "detail": "Profile updated successfully."}


@auth_router.get("/admin_profile")
async def get_profile(user: Annotated[User, Depends(get_admin)]):
   
    user = await User.filter(id=user.id).first()
    
    return {
        "name": user.name,
        "email": user.email,
        "created_at" : user.created_at
       
    }