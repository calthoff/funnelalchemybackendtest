from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime

class CampaignBase(BaseModel):
    # product_id: UUID
    name: str
    campaign_type: str
    is_paused: bool
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    campaign_manager_id: Optional[UUID] = None

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(BaseModel):
    # product_id: Optional[UUID]
    name: Optional[str]
    campaign_type: Optional[str]
    is_paused: Optional[bool]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    campaign_manager_id: Optional[UUID]

class CampaignRead(CampaignBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    total_leads: int = 0
    pushed_leads: int = 0

    class Config:
        from_attributes = True

class CampaignDashboardStats(BaseModel):
    campaign_name: str
    icp_used: List[str]
    leads_emailed: int
    positive_replies: int
    meetings_booked: int
    deals_closed: int
    sdr_running: List[str]

class CampaignDashboardStatsPage(BaseModel):
    items: List[CampaignDashboardStats]
    total: int 