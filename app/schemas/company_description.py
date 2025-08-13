from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class CompanyDescriptionBase(BaseModel):
    description: Optional[str] = None
    exclusion_criteria: Optional[str] = None

class CompanyDescriptionCreate(CompanyDescriptionBase):
    pass

class CompanyDescriptionUpdate(BaseModel):
    description: Optional[str] = None
    exclusion_criteria: Optional[str] = None

class CompanyDescriptionRead(CompanyDescriptionBase):
    id: UUID
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 