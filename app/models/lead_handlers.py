from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db import Base

class LeadHandler(Base):
    __tablename__ = 'lead_handlers'
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True)
    current_capacity = Column(Integer, default=0)  # How many leads this SDR is currently handling
    max_capacity = Column(Integer, default=100)  # How many leads this SDR can handle
    performance_score = Column(Float, default=0.0)  # How well this SDR is performing
    is_active = Column(Boolean, default=True)  # Whether this SDR is active
    notes = Column(String)  # Notes about this SDR
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())