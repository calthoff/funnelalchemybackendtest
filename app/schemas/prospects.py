from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime

class ProspectBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None

class ProspectCreate(ProspectBase):
    icp_id: Optional[UUID] = None
    persona_id: Optional[UUID] = None
    sales_rep_id: Optional[UUID] = None

class ProspectUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    icp_id: Optional[UUID] = None
    persona_id: Optional[UUID] = None
    sales_rep_id: Optional[UUID] = None
    current_score: Optional[int] = None
    initial_score: Optional[int] = None
    score_reason: Optional[str] = None
    score_period: Optional[str] = None
    suggested_sales_rep_reason: Optional[str] = None
    suggested_sales_rep_date: Optional[datetime] = None
    headshot_url: Optional[str] = None
    headshot_filename: Optional[str] = None

class ProspectRead(ProspectBase):
    id: UUID
    icp_id: Optional[UUID] = None
    persona_id: Optional[UUID] = None
    sales_rep_id: Optional[UUID] = None
    current_score: Optional[int] = 0
    initial_score: Optional[int] = 0
    score_reason: Optional[str] = None
    score_period: Optional[str] = None
    suggested_sales_rep_reason: Optional[str] = None
    suggested_sales_rep_date: Optional[datetime] = None
    headshot_url: Optional[str] = None
    headshot_filename: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True