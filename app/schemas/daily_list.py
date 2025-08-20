from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class DailyListBase(BaseModel):
    prospect_id: UUID
    contact_status: str = "Not contacted"
    notes: Optional[str] = None
    is_primary: bool = True

class DailyListCreate(DailyListBase):
    pass

class DailyListUpdate(BaseModel):
    contact_status: Optional[str] = None
    notes: Optional[str] = None
    removal_reason: Optional[str] = None
    removed_date: Optional[datetime] = None

class DailyListResponse(DailyListBase):
    id: UUID
    added_date: datetime
    removed_date: Optional[datetime] = None
    removal_reason: Optional[str] = None
    daily_batch_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 