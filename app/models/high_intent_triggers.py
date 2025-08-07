from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class HighIntentTrigger(Base):
    __tablename__ = 'high_intent_triggers'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    trigger_id = Column(String, nullable=False)
    trigger_value = Column(String)
    label = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 