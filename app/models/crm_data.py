from sqlalchemy import Column, DateTime, String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class CRMData(Base):
    __tablename__ = 'crm_data'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_companies_id = Column(UUID(as_uuid=True), ForeignKey('campaign_companies.id'), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=False)
    deal_name = Column(String, nullable=False)
    deal_stage = Column(String, nullable=False)
    crm_value = Column(Integer, nullable=False)
    close_date = Column(DateTime(timezone=True), nullable=False)
    crm_owner_id = Column(String, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=False)