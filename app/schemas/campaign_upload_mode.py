from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class CampaignUploadModeBase(BaseModel):
    campaign_id: UUID
    sdr_assignment_mode: Optional[str]
    daily_push_limit: Optional[int]

class CampaignUploadModeCreate(CampaignUploadModeBase):
    pass

class CampaignUploadModeUpdate(BaseModel):
    campaign_id: Optional[UUID]
    sdr_assignment_mode: Optional[str]
    daily_push_limit: Optional[int]
    
class CampaignUploadModeRead(CampaignUploadModeBase):
    id: UUID

    class Config:
        from_attributes = True 