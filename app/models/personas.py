from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from sqlalchemy.sql import func
from app.db import Base

class Persona(Base):
    __tablename__ = 'personas'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    score = Column(String)
    tech_stack = Column(JSONB)
    title_keywords = Column(JSONB)
    departments = Column(JSONB)
    seniority_levels = Column(JSONB)
    buying_role = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 