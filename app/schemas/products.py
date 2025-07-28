from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    name: str
    description: str

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]

class ProductRead(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True 