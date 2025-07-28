from sqlalchemy import Column, ForeignKey, String, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db import Base

class CampaignUploadMode(Base):
    __tablename__ = 'campaign_upload_mode'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.id'), nullable=False)
    sdr_assignment_mode = Column(String, nullable=True)
    daily_push_limit = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('campaign_id', name='uq_campaign_upload_mode_campaign_id'),
    )