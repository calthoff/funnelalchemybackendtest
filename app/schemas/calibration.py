from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID

class CalibrationSessionBase(BaseModel):
    id: str
    user_id: str
    status: str
    sample_size: int
    feedback_count: int
    approved_count: int
    rejected_count: int
    created_at: datetime
    updated_at: datetime

class CalibrationSessionCreate(BaseModel):
    sample_size: Optional[int] = 10

class CalibrationSessionRead(CalibrationSessionBase):
    original_weights: Optional[Dict[str, float]] = None
    current_weights: Optional[Dict[str, float]] = None
    adjusted_weights: Optional[Dict[str, float]] = None
    completed_at: Optional[datetime] = None

class CalibrationSampleBase(BaseModel):
    prospect_data: Dict[str, Any]
    original_score: int
    score_reason: Optional[str] = None
    component_scores: Optional[Dict[str, Any]] = None

class CalibrationSampleCreate(CalibrationSampleBase):
    session_id: str

class CalibrationSampleRead(CalibrationSampleBase):
    id: str
    session_id: str
    user_feedback: Optional[str] = None
    feedback_reason: Optional[str] = None
    feedback_at: Optional[datetime] = None
    created_at: datetime

class CalibrationFeedbackRequest(BaseModel):
    sample_id: str
    feedback: str  # 'approved' or 'rejected'
    reason: Optional[str] = None

class CalibrationCompleteRequest(BaseModel):
    action: str  # 'approve', 'reset', 'apply_weights'
    feedback_summary: Optional[str] = None

class CalibrationSampleResponse(BaseModel):
    session: CalibrationSessionRead
    samples: List[CalibrationSampleRead]
    total_samples: int
    feedback_count: int
    approved_count: int
    rejected_count: int