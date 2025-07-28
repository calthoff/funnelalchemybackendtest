from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class CampaignManagerBase(BaseModel):
    title: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = True

class CampaignManagerCreate(CampaignManagerBase):
    user_id: UUID

class CampaignManagerUpdate(BaseModel):
    title: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    is_active: Optional[bool]

class CampaignManagerRead(CampaignManagerBase):
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True 