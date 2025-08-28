from pydantic import BaseModel, Field
from typing import List, Any

class ScoringSettings(BaseModel):
    """Scoring criteria and ICP rules."""
    class Config:
        extra = "allow"

class Prospect(BaseModel):
    """Prospect data with prospect_id and arbitrary fields."""
    prospect_id: str
    class Config:
        extra = "allow"

class ScoringRequest(BaseModel):
    """Request with scoring settings and prospects list."""
    scoring_settings: ScoringSettings
    prospects: List[Any]

class ScoringResult(BaseModel):
    """Scoring result with prospect_id, score, and justification."""
    prospect_id: str
    score: int = Field(ge=0, le=100)
    justification: str
