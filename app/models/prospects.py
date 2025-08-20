from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy import UniqueConstraint

class Prospect(Base):
    __tablename__ = 'prospects'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    prospect_setting_id = Column(UUID(as_uuid=True), ForeignKey('prospect_settings.id'), nullable=True, index=True)
    sales_rep_id = Column(UUID(as_uuid=True), ForeignKey('sdrs.id'), nullable=True, index=True)
    
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    company_name = Column(String)
    job_title = Column(String)
    linkedin_url = Column(String)
    phone_number = Column(String)
    location = Column(String)
    department = Column(String)
    seniority = Column(String)
    
    source = Column(String)
    source_id = Column(String)
    
    current_score = Column(BigInteger, default=0)
    initial_score = Column(BigInteger, default=0)
    score_reason = Column(String)
    score_period = Column(String)
    
    suggested_sales_rep_reason = Column(String)
    suggested_sales_rep_date = Column(DateTime(timezone=True))
    
    headshot_url = Column(String)
    headshot_filename = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('email', 'source', name='unique_prospect_per_source'),
    ) 