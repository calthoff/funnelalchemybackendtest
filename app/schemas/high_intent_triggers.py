from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class HighIntentTriggerBase(BaseModel):
    trigger_id: str
    trigger_value: Optional[str] = None
    label: str
    category: str
    description: Optional[str] = None
    is_active: Optional[bool] = False

class HighIntentTriggerCreate(HighIntentTriggerBase):
    pass

class HighIntentTriggerUpdate(BaseModel):
    trigger_id: Optional[str] = None
    trigger_value: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class HighIntentTriggerRead(HighIntentTriggerBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True