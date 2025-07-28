from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class Campaign(Base):
    __tablename__ = 'campaigns'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    name = Column(String, nullable=False)
    campaign_type = Column(String, nullable=False)
    is_paused = Column(Boolean, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    campaign_manager_id = Column(UUID(as_uuid=True), ForeignKey('campaign_managers.user_id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())