from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class HighIntentEvent(Base):
    __tablename__ = 'high_intent_events'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey('prospects.id'), nullable=False, index=True)
    trigger_id = Column(String, nullable=False)
    event_value = Column(String)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    score_boost_applied = Column(Integer, default=95)
    previous_score = Column(Integer)
    new_score = Column(Integer)
    processed = Column(String, default='false')  # Using String like current style
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 