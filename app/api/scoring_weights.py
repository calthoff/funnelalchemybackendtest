from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.scoring_weights import ScoringWeightCreate, ScoringWeightUpdate, ScoringWeightRead
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/scoring-weights", tags=["scoring-weights"], redirect_slashes=False)

@router.get("/", response_model=ScoringWeightRead)
def get_scoring_weights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(scoring_weights_table.select())
            weights = result.fetchone()
            
            if not weights:
                return ScoringWeightRead(
                    id=uuid.uuid4(),
                    persona_fit_weight="40",
                    company_fit_weight="40", 
                    sales_data_weight="20",
                    updated_at=None
                )
            
            return ScoringWeightRead(**{k: weights._mapping[k] for k in weights._mapping.keys() if k in ScoringWeightRead.__fields__})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch scoring weights")

@router.post("/", response_model=ScoringWeightRead)
def create_scoring_weights(
    weights_data: ScoringWeightCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        weights_id = str(uuid.uuid4())
        
        insert_data = {
            'id': weights_id,
            'persona_fit_weight': weights_data.persona_fit_weight or "40",
            'company_fit_weight': weights_data.company_fit_weight or "40",
            'sales_data_weight': weights_data.sales_data_weight or "20",
            'updated_at': func.now()
        }
        
        with db.bind.connect() as conn:
            conn.execute(scoring_weights_table.insert().values(insert_data))
            conn.commit()
        
        return ScoringWeightRead(**insert_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create scoring weights")

@router.put("/", response_model=ScoringWeightRead)
def update_scoring_weights(
    weights_data: ScoringWeightUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        scoring_weights_table = get_table('scoring_weights', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            existing_weights = conn.execute(scoring_weights_table.select()).fetchone()
            
            if not existing_weights:
                weights_id = str(uuid.uuid4())
                insert_data = {
                    'id': weights_id,
                    'persona_fit_weight': weights_data.persona_fit_weight or "40",
                    'company_fit_weight': weights_data.company_fit_weight or "40", 
                    'sales_data_weight': weights_data.sales_data_weight or "20",
                    'updated_at': func.now()
                }
                conn.execute(scoring_weights_table.insert().values(insert_data))
            else:
                update_data = {}
                if weights_data.persona_fit_weight is not None:
                    update_data['persona_fit_weight'] = weights_data.persona_fit_weight
                if weights_data.company_fit_weight is not None:
                    update_data['company_fit_weight'] = weights_data.company_fit_weight
                if weights_data.sales_data_weight is not None:
                    update_data['sales_data_weight'] = weights_data.sales_data_weight
                update_data['updated_at'] = func.now()
                
                conn.execute(
                    scoring_weights_table.update()
                    .where(scoring_weights_table.c.id == existing_weights.id)
                    .values(update_data)
                )
            
            conn.commit()
            
            result = conn.execute(scoring_weights_table.select()).fetchone()
            return ScoringWeightRead(**{k: result._mapping[k] for k in result._mapping.keys() if k in ScoringWeightRead.__fields__})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update scoring weights") 