from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class CampaignCompany(Base):
    __tablename__ = 'campaign_companies'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, index=True)
    website = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    description = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    revenue_range = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    funding_round = Column(String, nullable=True)
    tech_stack = Column(String, nullable=True)
    location = Column(String, nullable=True)
    assigned_sdr = Column(UUID(as_uuid=True), ForeignKey('sdrs.id'), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())