from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    approval_mode: Optional[str] = "manual"
    is_verified: Optional[bool] = False
    verification_code: Optional[str] = None
    reset_token: Optional[str] = None
    reset_token_expires: Optional[datetime] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "admin"

class UserUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[str]
    approval_mode: Optional[str]
    password: Optional[str]
    reset_token: Optional[str]
    reset_token_expires: Optional[datetime]

class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    company_name: Optional[str] = None
    aws_customer_id: Optional[str] = None

    model_config = {"from_attributes": True} 