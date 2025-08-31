from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ScoringSettings(BaseModel):
    """Accepts any fields for scoring criteria (ICP rules)."""
    model_config = ConfigDict(extra="allow")


class Prospect(BaseModel):
    """
    Prospect data with at least an ID and arbitrary other fields.

    - Accepts both `prospect_id` and `id` on input (validation_alias="id")
    - Coerces the ID to string
    - Allows arbitrary extra fields
    """
    prospect_id: str = Field(..., validation_alias="id")
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("prospect_id", mode="before")
    @classmethod
    def _coerce_pid(cls, v):
        if v is None:
            raise ValueError("prospect_id is required")
        return str(v)


class ScoringRequest(BaseModel):
    """Request body model containing scoring settings and a list of prospects."""
    scoring_settings: ScoringSettings
    prospects: List[dict]  # each prospect is a free-shape JSON object


class ScoringResult(BaseModel):
    """
    Result model with:
    - prospect_id
    - score (0-100)
    - justification (1–2 sentences)
    """
    prospect_id: str
    score: int = Field(ge=0, le=100)
    justification: str


# ---------- Response models for internal use ----------
class ScoringMeta(BaseModel):
    request_id: str
    count: int
    ok: int
    ok_share: float
    error_counts: Dict[str, int]
    retries_total: int
    latency_s: float


class ScoringResponse(BaseModel):
    meta: ScoringMeta
    results: List[ScoringResult]
