from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class APIInfoBase(BaseModel):
    api_type: str
    api_key: str

class APIInfoCreate(APIInfoBase):
    pass

class APIInfoUpdate(BaseModel):
    api_key: Optional[str]

class APIInfoRead(APIInfoBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
