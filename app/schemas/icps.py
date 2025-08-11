from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime

class ICPBase(BaseModel):
    name: str
    industries: Optional[Dict[str, Any]] = None
    employee_size_range: Optional[Dict[str, Any]] = None
    arr_range: Optional[Dict[str, Any]] = None
    funding_stage: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    accounts: Optional[str] = None
    is_primary: Optional[bool] = False

class ICPCreate(ICPBase):
    pass

class ICPUpdate(BaseModel):
    name: Optional[str] = None
    industries: Optional[Dict[str, Any]] = None
    employee_size_range: Optional[Dict[str, Any]] = None
    arr_range: Optional[Dict[str, Any]] = None
    funding_stage: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    accounts: Optional[str] = None
    is_primary: Optional[bool] = None

class ICPRead(ICPBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True