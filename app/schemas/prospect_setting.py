from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class ProspectSettingBase(BaseModel):
    name: str
    company_description: str
    
    industries: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    employee_range: Optional[List[str]] = None
    revenue_range: Optional[List[str]] = None
    
    title_keywords: Optional[List[str]] = None
    seniority_levels: Optional[List[str]] = None
    buying_roles: Optional[List[str]] = None
    
    hiring_roles: Optional[List[str]] = None
    new_hire_titles: Optional[List[str]] = None
    funding_stages: Optional[List[str]] = None
    tech_adoption: Optional[List[str]] = None
    ma_events: Optional[List[str]] = None
    
    exclusion_criteria: Optional[str] = None

class ProspectSettingCreate(ProspectSettingBase):
    pass

class ProspectSettingUpdate(BaseModel):
    name: Optional[str] = None
    company_description: Optional[str] = None
    
    industries: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    employee_range: Optional[List[str]] = None
    revenue_range: Optional[List[str]] = None
    
    title_keywords: Optional[List[str]] = None
    seniority_levels: Optional[List[str]] = None
    buying_roles: Optional[List[str]] = None
    
    hiring_roles: Optional[List[str]] = None
    new_hire_titles: Optional[List[str]] = None
    funding_stages: Optional[List[str]] = None
    tech_adoption: Optional[List[str]] = None
    ma_events: Optional[List[str]] = None
    
    exclusion_criteria: Optional[str] = None

class ProspectSettingResponse(ProspectSettingBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 