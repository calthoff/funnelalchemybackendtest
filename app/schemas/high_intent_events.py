from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class HighIntentEventBase(BaseModel):
    prospect_id: UUID
    trigger_id: str
    event_value: Optional[str] = None
    score_boost_applied: Optional[int] = 95
    previous_score: Optional[int] = None
    new_score: Optional[int] = None
    processed: Optional[str] = "false"
    processed_at: Optional[datetime] = None

class HighIntentEventCreate(HighIntentEventBase):
    pass

class HighIntentEventUpdate(BaseModel):
    prospect_id: Optional[UUID] = None
    trigger_id: Optional[str] = None
    event_value: Optional[str] = None
    score_boost_applied: Optional[int] = None
    previous_score: Optional[int] = None
    new_score: Optional[int] = None
    processed: Optional[str] = None
    processed_at: Optional[datetime] = None

class HighIntentEventRead(HighIntentEventBase):
    id: UUID
    detected_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True