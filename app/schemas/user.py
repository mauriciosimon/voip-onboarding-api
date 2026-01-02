from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# Auth schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    sip_extension: str  # Extension created manually in FreePBX
    sip_password: str   # SIP password from FreePBX


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


# User response schemas
class UserResponse(BaseModel):
    id: int
    email: str
    sip_extension: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# SIP credentials schema
class SIPCredentials(BaseModel):
    username: str  # extension number
    password: str
    domain: str
    port: int
    transport: str

    # Additional config for Linphone
    display_name: Optional[str] = None
    auth_username: Optional[str] = None
