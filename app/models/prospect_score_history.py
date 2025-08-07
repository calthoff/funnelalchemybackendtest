from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from sqlalchemy.sql import func
from app.db import Base

class ProspectScoreHistory(Base):
    __tablename__ = 'prospect_score_history'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey('prospects.id'), nullable=False, index=True)
    score_history = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 