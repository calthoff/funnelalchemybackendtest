from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy import UniqueConstraint

class Lead(Base):
    __tablename__ = 'leads'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_company_campaign_map_id = Column(UUID(as_uuid=True), ForeignKey('campaign_company_campaign_map.id'), nullable=True, index=True)
    icp_id = Column(UUID(as_uuid=True), ForeignKey('icps.id'), nullable=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    company_name = Column(String)
    job_title = Column(String)
    linkedin_url = Column(String)
    phone_number = Column(String)
    location = Column(String)
    department = Column(String)
    seniority = Column(String)
    personal_label = Column(String)
    source_notes = Column(String)
    lead_score = Column(Integer)
    personalization = Column(JSONB)
    clay_enrichment = Column(JSONB)
    enrichment_source = Column(String)
    enriched_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('email', 'campaign_company_campaign_map_id', name='unique_lead_per_mapping'),
    )