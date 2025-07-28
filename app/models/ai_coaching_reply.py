from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base

class AICoachingReply(Base):
    __tablename__ = 'ai_coaching_replies'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    sdr_id = Column(UUID(as_uuid=True), ForeignKey('sdrs.id'), nullable=False)
    reply = Column(Text, nullable=False)
    ai_quality_score = Column(Integer, nullable=False)
    coaching_tags = Column(ARRAY(String), nullable=True)
    suggested_rewrite = Column(Text, nullable=True)
    reply_lag_minutes = Column(Integer, nullable=True)
    reply_type = Column(String(50), nullable=True)
    datetime_sent = Column(DateTime, nullable=False)
    meeting_booked = Column(Boolean, nullable=False) 