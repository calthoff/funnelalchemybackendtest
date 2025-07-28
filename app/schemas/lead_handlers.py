from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class LeadHandlerBase(BaseModel):
    current_capacity: Optional[int] = 0
    max_capacity: Optional[int] = 100
    performance_score: Optional[float] = 0.0
    is_active: Optional[bool] = True
    notes: Optional[str] = None

class LeadHandlerCreate(LeadHandlerBase):
    user_id: UUID

class LeadHandlerUpdate(BaseModel):
    current_capacity: Optional[int]
    max_capacity: Optional[int]
    performance_score: Optional[float]
    is_active: Optional[bool]
    notes: Optional[str]

class LeadHandlerRead(LeadHandlerBase):
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True 