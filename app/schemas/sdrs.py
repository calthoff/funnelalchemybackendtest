from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional
from datetime import datetime

class SDRBase(BaseModel):
    name: str
    role: Optional[str] = None
    territory: Optional[str] = None
    max_capacity: Optional[int] = 100
    notes: Optional[str] = None
    status: Optional[str] = None

class SDRCreate(SDRBase):
    pass

class SDRUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    territory: Optional[str] = None
    max_capacity: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class SDR(SDRBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class SDRDashboardStats(BaseModel):
    sdr_name: str
    leads_emailed: int
    positive_replies: int
    meetings_booked: int
    deals_closed: int
    campaigns_touched: int

class SDRDashboardStatsPage(BaseModel):
    items: list[SDRDashboardStats]
    total: int 