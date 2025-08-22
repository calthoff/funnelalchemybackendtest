from pydantic import BaseModel, validator
from uuid import UUID
from typing import Optional, Dict, Any, List
from datetime import datetime

class ActivityRead(BaseModel):
    id: str
    prospect_id: str
    type: str
    source: Optional[str] = None
    description: str
    timestamp: Optional[datetime] = None

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
    reply_status: Optional[str] = None
    reply_content: Optional[str] = None
    reply_sentiment: Optional[str] = None
    reply_date: Optional[datetime] = None
    contacted_date: Optional[datetime] = None
    funding_stage: Optional[str] = None
    funding_amount: Optional[str] = None
    funding_date: Optional[datetime] = None

class ProspectCreate(ProspectBase):
    prospect_setting_id: Optional[UUID] = None
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
    current_score: Optional[int] = None
    initial_score: Optional[int] = None
    score_reason: Optional[str] = None
    score_period: Optional[str] = None
    suggested_sales_rep_reason: Optional[str] = None
    suggested_sales_rep_date: Optional[datetime] = None
    sales_rep_id: Optional[UUID] = None
    headshot_url: Optional[str] = None
    headshot_filename: Optional[str] = None
    reply_status: Optional[str] = None
    reply_content: Optional[str] = None
    reply_sentiment: Optional[str] = None
    reply_date: Optional[datetime] = None
    contacted_date: Optional[datetime] = None
    funding_stage: Optional[str] = None
    funding_amount: Optional[str] = None
    funding_date: Optional[datetime] = None

    @validator('funding_date', 'reply_date', 'contacted_date', 'suggested_sales_rep_date', pre=True)
    def convert_empty_strings_to_none(cls, v):
        if v == "":
            return None
        return v

class ProspectRead(ProspectBase):
    id: UUID
    prospect_setting_id: Optional[UUID] = None
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
    activities: Optional[List[ActivityRead]] = []

    class Config:
        from_attributes = True