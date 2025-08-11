from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class NotificationBase(BaseModel):
    sales_rep_id: UUID
    description: str
    is_read: bool

class NotificationCreate(NotificationBase):
    pass

class NotificationUpdate(BaseModel):
    sales_rep_id: Optional[UUID] = None
    description: Optional[str] = None
    is_read: Optional[bool] = None

class NotificationRead(BaseModel):
    id: UUID
    is_read: bool

class NotificationRead(NotificationBase):
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True