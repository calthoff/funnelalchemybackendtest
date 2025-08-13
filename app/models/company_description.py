from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class CompanyDescription(Base):
    __tablename__ = 'company_descriptions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    description = Column(Text)
    exclusion_criteria = Column(Text)  # New field for "Companies You Don't Sell To"
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 