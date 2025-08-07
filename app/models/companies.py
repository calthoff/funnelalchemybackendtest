from sqlalchemy import Column, String, DateTime, UUID
from sqlalchemy.sql import func
from app.db import Base


class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()) 