from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    phone: Optional[str] = None
    role: Literal["sys_admin", "firm_admin"]
    firm_id: Optional[str] = None  # Mandatory for firm_admin, None for sys_admin


class UserLoginRequest(BaseModel):
    username_or_email: str
    password: str


class SwitchFirmRequest(BaseModel):
    target_firm_id: str = Field(..., description="Target firm ID to switch into")


class UserProfileOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str
    phone: Optional[str]
    role: str
    firm_id: Optional[str]
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut