from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.mutable import MutableList
import uuid
from sqlalchemy.sql import func
from app.db import Base

class LeadProcess(Base):
    __tablename__ = 'lead_processes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=False)
    status = Column(String, nullable=False)
    reply_text_array = Column(MutableList.as_mutable(JSONB), nullable=True, default=list)
    reply_classification = Column(String, nullable=True)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now())