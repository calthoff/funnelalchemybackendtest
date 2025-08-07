from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from sqlalchemy.sql import func
from app.db import Base

class ICP(Base):
    __tablename__ = 'icps'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    industries = Column(JSONB)
    employee_size_range = Column(JSONB)
    arr_range = Column(JSONB)
    funding_stage = Column(JSONB)
    location = Column(JSONB)
    description = Column(String)
    accounts = Column(String)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())