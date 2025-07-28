from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class LeadActivityBase(BaseModel):
    campaign_lead_id: UUID
    type: str
    source: str
    description: str

class LeadActivityCreate(LeadActivityBase):
    pass

class LeadActivityUpdate(BaseModel):
    type: Optional[str]
    source: Optional[str]
    description: Optional[str]

class LeadActivityRead(LeadActivityBase):
    id: UUID

    class Config:
        from_attributes = True 