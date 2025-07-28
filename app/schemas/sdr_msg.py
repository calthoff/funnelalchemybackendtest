from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class SDRMsgBase(BaseModel):
    user_id: UUID
    lead_id: Optional[UUID] = None
    lead_ids: Optional[List[UUID]] = None
    message: str
    type: str
    status: str = 'unread'

class SDRMsgCreate(SDRMsgBase):
    pass

class SDRMsgUpdate(BaseModel):
    message: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None

class SDRMsg(SDRMsgBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True 