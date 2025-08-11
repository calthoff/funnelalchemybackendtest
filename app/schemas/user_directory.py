from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserDirectoryBase(BaseModel):
    email: EmailStr
    schema_name: str
    company_name: str
        
class UserDirectoryCreate(UserDirectoryBase):
    pass

class UserDirectoryUpdate(BaseModel):
    email: Optional[EmailStr]
    schema_name: Optional[str]
    company_name: Optional[str]

class UserDirectoryRead(UserDirectoryBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True