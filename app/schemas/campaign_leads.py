from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class CampaignLeadBase(BaseModel):
    campaign_id: UUID
    lead_id: UUID
    handler_id: Optional[UUID] = None
    is_primary: Optional[bool] = False
class CampaignLeadCreate(CampaignLeadBase):
    pass

class CampaignLeadUpdate(BaseModel):
    handler_id: Optional[UUID]

class CampaignLeadRead(CampaignLeadBase):
    id: UUID

    class Config:
        from_attributes = True
