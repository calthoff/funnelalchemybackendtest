from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.company_description import CompanyDescriptionCreate, CompanyDescriptionUpdate, CompanyDescriptionRead
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/company-description", tags=["company-description"], redirect_slashes=False)

@router.get("/", response_model=CompanyDescriptionRead)
def get_company_description(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(company_description_table.select())
            description = result.fetchone()
            
            if not description:
                return CompanyDescriptionRead(
                    id=uuid.uuid4(),
                    description="",
                    exclusion_criteria="",
                    scoring_prompt="",
                    updated_at=None
                )
            
            return CompanyDescriptionRead(**{k: description._mapping[k] for k in description._mapping.keys() if k in CompanyDescriptionRead.__fields__})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch company description")

@router.put("/", response_model=CompanyDescriptionRead)
def update_company_description(
    description_data: CompanyDescriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            existing_description = conn.execute(company_description_table.select()).fetchone()
            
            if not existing_description:
                description_id = str(uuid.uuid4())
                insert_data = {
                    'id': description_id,
                    'description': description_data.description or "",
                    'exclusion_criteria': description_data.exclusion_criteria or "",
                    'scoring_prompt': description_data.scoring_prompt or "",
                    'updated_at': func.now()
                }
                conn.execute(company_description_table.insert().values(insert_data))
            else:
                update_data = {}
                if description_data.description is not None:
                    update_data['description'] = description_data.description
                if description_data.exclusion_criteria is not None:
                    update_data['exclusion_criteria'] = description_data.exclusion_criteria
                if description_data.scoring_prompt is not None:
                    update_data['scoring_prompt'] = description_data.scoring_prompt
                update_data['updated_at'] = func.now()
                
                conn.execute(
                    company_description_table.update()
                    .where(company_description_table.c.id == existing_description.id)
                    .values(update_data)
                )
            
            conn.commit()
            
            result = conn.execute(company_description_table.select()).fetchone()
            return CompanyDescriptionRead(**{k: result._mapping[k] for k in result._mapping.keys() if k in CompanyDescriptionRead.__fields__})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update company description") 