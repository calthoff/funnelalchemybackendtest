from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class CampaignICPBase(BaseModel):
    campaign_id: UUID
    icp_id: UUID

class CampaignICPCreate(CampaignICPBase):
    pass

class CampaignICPUpdate(BaseModel):
    campaign_id: Optional[UUID]
    icp_id: Optional[UUID]

class CampaignICPRead(CampaignICPBase):
    id: UUID

    class Config:
        from_attributes = True 