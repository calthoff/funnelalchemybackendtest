from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class ProspectActivity(Base):
    __tablename__ = 'prospect_activities'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    prospect_id = Column(UUID(as_uuid=True), ForeignKey('prospects.id'), nullable=False, index=True)
    type = Column(String, nullable=False)  # e.g., sent, opened, replied, etc.
    source = Column(String, nullable=False)  # e.g., email, phone, etc.
    description = Column(String, nullable=False)  # e.g., sent email to John Doe, replied to email from Jane Smith, etc.
    timestamp = Column(DateTime(timezone=True), server_default=func.now()) 