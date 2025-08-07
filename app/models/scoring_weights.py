from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class ScoringWeight(Base):
    __tablename__ = 'scoring_weights'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    persona_fit_weight = Column(String)
    company_fit_weight = Column(String)
    sales_data_weight = Column(String)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 