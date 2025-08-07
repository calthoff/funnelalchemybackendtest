from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class SDR(Base):
    __tablename__ = 'sdrs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    territory = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Text, nullable=True)
    headshot_url = Column(String, nullable=True)
    headshot_filename = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 