from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base

class CampaignICP(Base):
    __tablename__ = 'campaign_icps'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id'), nullable=False)
    icp_id = Column(UUID(as_uuid=True), ForeignKey('icps.id'), nullable=False) 