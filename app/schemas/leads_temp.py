from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl

class LeadTempBase(BaseModel):
    campaign_id: UUID
    first_name: str
    last_name: str
    email: str
    company_name: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_round: Optional[str] = None
    tech_stack: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[str] = None
    seniority: Optional[str] = None
    personal_label: Optional[str] = None
    source_notes: Optional[str] = None
    lead_score: Optional[int] = None
    personalization: Optional[dict] = None
    clay_enrichment: Optional[dict] = None
    enrichment_source: Optional[str] = None
    enriched_at: Optional[datetime] = None
    pushed_status: str = 'Not Pushed'

class LeadTempCreate(LeadTempBase):
    pass

class LeadTempUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    revenue_range: Optional[str] = None
    company_size: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_round: Optional[str] = None
    tech_stack: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    phone_number: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[str] = None
    seniority: Optional[str] = None
    personal_label: Optional[str] = None
    source_notes: Optional[str] = None
    lead_score: Optional[int] = None
    personalization: Optional[dict] = None
    clay_enrichment: Optional[dict] = None
    enrichment_source: Optional[str] = None
    enriched_at: Optional[datetime] = None
    pushed_status: Optional[str] = None

class LeadTempRead(LeadTempBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 