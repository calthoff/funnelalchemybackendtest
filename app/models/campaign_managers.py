from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db import Base

class CampaignManager(Base):
    __tablename__ = 'campaign_managers'
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True)
    title = Column(String)  # Title of the campaign manager
    phone = Column(String)  # Phone number of the campaign manager
    notes = Column(String)  # Notes about the campaign manager
    is_active = Column(Boolean, default=True)  # Whether the campaign manager is active
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())