from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy import UniqueConstraint

class Prospect(Base):
    __tablename__ = 'prospects'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Foreign Keys
    icp_id = Column(UUID(as_uuid=True), ForeignKey('icps.id'), nullable=True, index=True)
    persona_id = Column(UUID(as_uuid=True), ForeignKey('personas.id'), nullable=True, index=True)
    sales_rep_id = Column(UUID(as_uuid=True), ForeignKey('sdrs.id'), nullable=True, index=True)
    
    # Basic Information
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
    
    # Source Information
    source = Column(String)  # 'apollo', 'clay', 'csv', 'linkedin'
    source_id = Column(String)  # External ID from source
    
    # Scoring Information
    current_score = Column(BigInteger, default=0)
    initial_score = Column(BigInteger, default=0)
    score_reason = Column(String)
    score_period = Column(String)
    
    # Assignment Information
    suggested_sales_rep_reason = Column(String)
    suggested_sales_rep_date = Column(DateTime(timezone=True))
    
    # Image Information
    headshot_url = Column(String)
    headshot_filename = Column(String)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('email', 'source', name='unique_prospect_per_source'),
    ) 