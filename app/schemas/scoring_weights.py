from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class ScoringWeightBase(BaseModel):
    persona_fit_weight: Optional[str] = None
    company_fit_weight: Optional[str] = None
    sales_data_weight: Optional[str] = None

class ScoringWeightCreate(ScoringWeightBase):
    pass

class ScoringWeightUpdate(BaseModel):
    persona_fit_weight: Optional[str] = None
    company_fit_weight: Optional[str] = None
    sales_data_weight: Optional[str] = None

class ScoringWeightRead(ScoringWeightBase):
    id: UUID
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True