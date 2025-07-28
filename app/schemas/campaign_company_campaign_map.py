from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class CampaignCompanyCampaignMapBase(BaseModel):
    campaign_company_id: UUID
    campaign_id: UUID
    company_score: int
    context: str
    isTier1: bool
    isCold: bool
class CampaignCompanyCampaignMapCreate(CampaignCompanyCampaignMapBase):
    pass

class CampaignCompanyCampaignMapUpdate(CampaignCompanyCampaignMapBase):
    company_score: int
    context: str
    isTier1: bool
    isCold: bool

class CampaignCompanyCampaignMap(CampaignCompanyCampaignMapBase):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True 