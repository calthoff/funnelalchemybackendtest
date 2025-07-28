from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
from sqlalchemy.sql import func
from app.db import Base

class SDRMsg(Base):
    __tablename__ = 'sdr_msg'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('leads.id'), nullable=True)
    lead_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default='unread')
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 