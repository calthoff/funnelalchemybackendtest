from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl

class LeadBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    personal_label: Optional[str] = None
    source_notes: Optional[str] = None
    lead_score: Optional[int] = None
    personalization: Optional[Dict[str, Any]] = None
    clay_enrichment: Optional[Dict[str, Any]] = None
    enrichment_source: Optional[str] = None
    enriched_at: Optional[datetime] = None
    icp_id: Optional[UUID] = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    personal_label: Optional[str] = None
    source_notes: Optional[str] = None
    lead_score: Optional[int] = None
    personalization: Optional[Dict[str, Any]] = None
    clay_enrichment: Optional[Dict[str, Any]] = None
    enrichment_source: Optional[str] = None
    enriched_at: Optional[datetime] = None
    icp_id: Optional[UUID] = None
class LeadRead(LeadBase):
    id: UUID
    campaign_company_campaign_map_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 