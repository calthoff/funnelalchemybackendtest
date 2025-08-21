from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class ProspectSetting(Base):
    __tablename__ = 'prospect_settings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    name = Column(String, nullable=False)
    company_description = Column(Text, nullable=True)
    exclusion_criteria = Column(Text, nullable=True)
    
    industries = Column(JSONB, nullable=True)
    employee_range = Column(JSONB, nullable=True)
    revenue_range = Column(JSONB, nullable=True)
    
    title_keywords = Column(JSONB, nullable=True)
    seniority_levels = Column(JSONB, nullable=True)
    buying_roles = Column(JSONB, nullable=True)
    
    hiring_roles = Column(JSONB, nullable=True)
    new_hire_titles = Column(JSONB, nullable=True)
    funding_stages = Column(JSONB, nullable=True)
    tech_adoption = Column(JSONB, nullable=True)
    ma_events = Column(JSONB, nullable=True)
    
    scoring_prompt = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
