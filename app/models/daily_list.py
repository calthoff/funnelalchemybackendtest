from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class DailyList(Base):
    __tablename__ = 'daily_list'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey('prospects.id'), nullable=False, index=True)
    added_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    removed_date = Column(DateTime(timezone=True), nullable=True)
    removal_reason = Column(String, nullable=True)
    contact_status = Column(String, default='Not contacted')
    notes = Column(Text, nullable=True)
    is_primary = Column(Boolean, default=True)
    daily_batch_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 