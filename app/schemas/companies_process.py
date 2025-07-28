from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class CompaniesProcessBase(BaseModel):
    campaign_company_campaign_map_id: UUID
    status: str
    reason: Optional[str] = None

class CompaniesProcessCreate(CompaniesProcessBase):
    pass

class CompaniesProcessRead(CompaniesProcessBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CompaniesProcessUpdate(BaseModel):        
    status: Optional[str] = None
    reason: Optional[str] = None

class CompaniesProcessRead(CompaniesProcessBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CompaniesProcessUpdate(BaseModel):            
    status: Optional[str] = None
    reason: Optional[str] = None

class CompaniesProcessRead(CompaniesProcessBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        