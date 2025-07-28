from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class LogBase(BaseModel):
    campaign_id: UUID
    entity_type: str
    entity_id: UUID
    destination: str
    sync_action: str
    sync_status: str
    error_message: Optional[str] = None
    payload: Optional[dict] = None

class LogCreate(LogBase):   
    pass

class LogUpdate(BaseModel):
    sync_status: Optional[str] = None
    error_message: Optional[str] = None
    payload: Optional[dict] = None

class LogRead(LogBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True