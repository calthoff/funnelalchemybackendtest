from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field, validator
from app.schemas.leads import LeadRead

class CampaignCompanyBase(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    assigned_sdr: Optional[UUID] = None
    created_at: Optional[datetime] = None
    assigned_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_round: Optional[str] = None
    tech_stack: Optional[str] = None
    location: Optional[str] = None

class CampaignCompanyCreate(CampaignCompanyBase):
    website: str
    campaign_id: UUID

class CampaignCompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    assigned_sdr: Optional[UUID] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_round: Optional[str] = None
    tech_stack: Optional[str] = None
    location: Optional[str] = None
    stage: Optional[str] = None
    assigned_date: Optional[datetime] = None

    @validator('assigned_sdr', pre=True)
    def validate_assigned_sdr(cls, v):
        if v == "" or v is None:
            return None
        return v

class ApproveCompaniesRequest(BaseModel):
    company_ids: List[UUID]

class CampaignCompanyRead(CampaignCompanyBase):
    id: UUID
    leads: Optional[List[Dict[str, Any]]] = []
    stage: Optional[str] = None
    reason: Optional[str] = None
    score_reason: Optional[str] = None
    isTier1: bool = False
    isCold: bool = False
    company_score: Optional[int] = None
    class Config:
        from_attributes = True

class InfiniteBatchResponse(BaseModel):
    count: Dict[str, int]
    class Config:
        extra = "allow"