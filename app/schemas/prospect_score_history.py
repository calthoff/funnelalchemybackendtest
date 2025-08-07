from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime

class ProspectScoreHistoryBase(BaseModel):
    prospect_id: UUID
    score_history: Optional[Dict[str, Any]] = None

class ProspectScoreHistoryCreate(ProspectScoreHistoryBase):
    pass

class ProspectScoreHistoryUpdate(BaseModel):
    prospect_id: Optional[UUID] = None
    score_history: Optional[Dict[str, Any]] = None

class ProspectScoreHistoryRead(ProspectScoreHistoryBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True