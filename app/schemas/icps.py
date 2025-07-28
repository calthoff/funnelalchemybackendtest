from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime

class ICPBase(BaseModel):
    name: str
    criteria: dict

class ICPCreate(ICPBase):
    pass

class ICPUpdate(BaseModel):
    name: Optional[str]
    criteria: Optional[dict]

class ICPRead(ICPBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ICPDashboardStats(BaseModel):
    icp_name: str
    deals_closed: int
    positive_replies: int
    meetings_booked: int
    close_rate: float
    sdrs_assigned: List[str]

class ICPDashboardStatsPage(BaseModel):
    items: List[ICPDashboardStats]
    total: int 