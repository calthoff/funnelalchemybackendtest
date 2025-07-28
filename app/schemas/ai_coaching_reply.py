from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class AICoachingReply(BaseModel):
    id: UUID
    sdr_id: UUID
    reply: str
    ai_quality_score: int
    coaching_tags: Optional[List[str]] = None
    suggested_rewrite: Optional[str] = None
    reply_lag_minutes: Optional[int] = None
    reply_type: Optional[str] = None
    datetime_sent: datetime
    meeting_booked: bool

class AICoachingRepliesResponse(BaseModel):
    sdr_id: UUID
    sdr_name: str
    replies: List[AICoachingReply] 