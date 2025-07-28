from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class LeadTemp(Base):
    __tablename__ = 'leads_temp'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id'), nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    company_name = Column(String)
    website = Column(String)
    description = Column(String)
    industry = Column(String)
    revenue_range = Column(String)
    linkedin_url = Column(String)
    funding_round = Column(String)
    tech_stack = Column(String)
    location = Column(String)
    job_title = Column(String)
    phone_number = Column(String)
    company_size = Column(String)
    department = Column(String)
    tags = Column(String)
    seniority = Column(String)
    personal_label = Column(String)
    source_notes = Column(String) 
    lead_score = Column(Integer)
    personalization = Column(JSONB)
    clay_enrichment = Column(JSONB)
    enrichment_source = Column(String)
    enriched_at = Column(DateTime(timezone=True))
    pushed_status = Column(String, default='Not Pushed', nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())