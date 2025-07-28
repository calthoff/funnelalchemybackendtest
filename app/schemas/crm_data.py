from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class CRMDataBase(BaseModel):
    campaign_companies_id: UUID
    lead_id: UUID
    deal_name: str
    deal_stage: str
    crm_value: int
    close_date: datetime
    crm_owner_id: str
    last_synced_at: datetime

class CRMDataCreate(CRMDataBase):
    pass

class CRMDataUpdate(BaseModel):
    deal_name: Optional[str] = None
    deal_stage: Optional[str] = None
    crm_value: Optional[int] = None
    close_date: Optional[datetime] = None
    crm_owner_id: Optional[str] = None
    last_synced_at: Optional[datetime] = None

class CRMData(CRMDataBase):
    id: UUID

    class Config:
        from_attributes = True 