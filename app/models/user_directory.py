from sqlalchemy import Column, String, Integer
from app.db import Base

class UserDirectory(Base):
    __tablename__ = 'user_directory'
    __table_args__ = {'schema': 'public'}
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    schema_name = Column(String, nullable=False)
    company_name = Column(String, nullable=False) 