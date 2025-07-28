from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base

class APIInfo(Base):
    __tablename__ = 'api_info'
    # __table_args__ = {'schema': None}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_type = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 