from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime

class ReplyData(BaseModel):
    content: str
    timestamp: str
    reply_classification: str

class LeadProcessBase(BaseModel):
    lead_id: UUID
    status: str
    reply_text_array: Optional[List[ReplyData]] = None
    reply_classification: Optional[str] = None
    last_updated_at: Optional[datetime] = None

class LeadProcessCreate(LeadProcessBase):
    pass

class LeadProcessUpdate(BaseModel):
    status: Optional[str] = None
    reply_text_array: Optional[List[ReplyData]] = None
    reply_classification: Optional[str] = None
    last_updated_at: Optional[datetime] = None

class LeadProcessRead(LeadProcessBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True