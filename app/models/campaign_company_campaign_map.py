from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class CampaignCompanyCampaignMap(Base):
    __tablename__ = 'campaign_company_campaign_map'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_company_id = Column(UUID(as_uuid=True), ForeignKey('campaign_companies.id'), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id'), nullable=False)
    company_score = Column(Integer, nullable=True)
    context = Column(String, nullable=True)
    isCold = Column(Boolean, default=False)
    isTier1 = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('campaign_company_id', 'campaign_id', name='_campaign_company_campaign_uc'),
    ) 