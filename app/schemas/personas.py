from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any, List
from datetime import datetime

class PersonaBase(BaseModel):
    name: str
    score: Optional[str] = None
    tech_stack: Optional[Dict[str, Any]] = None
    title_keywords: Optional[Dict[str, Any]] = None
    departments: Optional[Dict[str, Any]] = None
    seniority_levels: Optional[Dict[str, Any]] = None
    buying_role: Optional[Dict[str, Any]] = None

class PersonaCreate(PersonaBase):
    pass

class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    score: Optional[str] = None
    tech_stack: Optional[Dict[str, Any]] = None
    title_keywords: Optional[Dict[str, Any]] = None
    departments: Optional[Dict[str, Any]] = None
    seniority_levels: Optional[Dict[str, Any]] = None
    buying_role: Optional[Dict[str, Any]] = None

class PersonaRead(PersonaBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True