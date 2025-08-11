from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class ProspectActivityBase(BaseModel):
    prospect_id: UUID
    type: str
    source: str
    description: str

class ProspectActivityCreate(ProspectActivityBase):
    pass

class ProspectActivityUpdate(BaseModel):
    prospect_id: Optional[UUID] = None
    type: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None

class ProspectActivityRead(ProspectActivityBase):
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True