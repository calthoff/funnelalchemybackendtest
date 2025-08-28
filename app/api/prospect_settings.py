from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import uuid
from datetime import datetime

from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.prospect_setting import (
    ProspectSettingCreate,
    ProspectSettingUpdate,
    ProspectSettingResponse
)
from app.utils.db_utils import get_table

router = APIRouter(prefix="/prospect-settings", tags=["prospect-settings"])


@router.get("/", response_model=List[ProspectSettingResponse])
def get_prospect_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(prospect_settings_table.select())
            prospect_settings = result.fetchall()
        
        return [
            ProspectSettingResponse(
                id=setting._mapping['id'],
                name=setting._mapping['name'],
                company_description=setting._mapping.get('company_description'),
                industries=setting._mapping.get('industries'),
                locations=setting._mapping.get('locations'),
                employee_range=setting._mapping.get('employee_range'),
                revenue_range=setting._mapping.get('revenue_range'),
                title_keywords=setting._mapping.get('title_keywords'),
                seniority_levels=setting._mapping.get('seniority_levels'),
                buying_roles=setting._mapping.get('buying_roles'),
                hiring_roles=setting._mapping.get('hiring_roles'),
                new_hire_titles=setting._mapping.get('new_hire_titles'),
                funding_stages=setting._mapping.get('funding_stages'),
                tech_adoption=setting._mapping.get('tech_adoption'),
                ma_events=setting._mapping.get('ma_events'),
                exclusion_criteria=setting._mapping.get('exclusion_criteria'),
                created_at=setting._mapping['created_at'],
                updated_at=setting._mapping.get('updated_at')
            ) for setting in prospect_settings
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch prospect settings: {str(e)}"
        )

@router.post("/", response_model=ProspectSettingResponse)
def create_prospect_setting(
    prospect_setting_data: ProspectSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            existing_settings = conn.execute(prospect_settings_table.select()).fetchall()
            
            if existing_settings:
                existing_setting = existing_settings[0]
                return update_existing_prospect_setting(existing_setting, prospect_setting_data, prospect_settings_table, conn)
            else:
                return create_new_prospect_setting(prospect_setting_data, prospect_settings_table, conn)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prospect setting: {str(e)}"
        )
def update_existing_prospect_setting(existing_setting, data: ProspectSettingCreate, table, conn):
    if not data.company_description or not data.company_description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company description is required"
        )

    update_data = data.dict()
    
    for field in ['company_description', 'exclusion_criteria']:
        if field in update_data and update_data[field] == "":
            pass
        elif field in update_data and update_data[field] is None:
            update_data.pop(field)
    
    available_columns = table.columns.keys()
    filtered_update_data = {k: v for k, v in update_data.items() if k in available_columns}
    
    filtered_update_data['updated_at'] = datetime.utcnow()
    
    update_stmt = table.update().where(table.c.id == existing_setting._mapping['id']).values(**filtered_update_data)
    conn.execute(update_stmt)
    conn.commit()
    
    updated_result = conn.execute(
        table.select().where(table.c.id == existing_setting._mapping['id'])
    )
    updated_setting = updated_result.fetchone()
    
    return ProspectSettingResponse(
        id=updated_setting._mapping['id'],
        name=updated_setting._mapping['name'],
        company_description=updated_setting._mapping.get('company_description'),
        industries=updated_setting._mapping.get('industries'),
        locations=updated_setting._mapping.get('locations'),
        employee_range=updated_setting._mapping.get('employee_range'),
        revenue_range=updated_setting._mapping.get('revenue_range'),
        title_keywords=updated_setting._mapping.get('title_keywords'),
        seniority_levels=updated_setting._mapping.get('seniority_levels'),
        buying_roles=updated_setting._mapping.get('buying_roles'),
        hiring_roles=updated_setting._mapping.get('hiring_roles'),
        new_hire_titles=updated_setting._mapping.get('new_hire_titles'),
        funding_stages=updated_setting._mapping.get('funding_stages'),
        tech_adoption=updated_setting._mapping.get('tech_adoption'),
        ma_events=updated_setting._mapping.get('ma_events'),
        exclusion_criteria=updated_setting._mapping.get('exclusion_criteria'),
        created_at=updated_setting._mapping['created_at'],
        updated_at=updated_setting._mapping.get('updated_at')
    )

def create_new_prospect_setting(data: ProspectSettingCreate, table, conn):
    if not data.company_description or not data.company_description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company description is required"
        )
    
    prospect_setting_dict = data.dict()
    prospect_setting_dict['id'] = str(uuid.uuid4())
    
    available_columns = table.columns.keys()
    filtered_data = {k: v for k, v in prospect_setting_dict.items() if k in available_columns}
    
    insert_stmt = table.insert().values(**filtered_data)
    result = conn.execute(insert_stmt)
    conn.commit()
    
    new_prospect_setting = conn.execute(
        table.select().where(table.c.id == filtered_data['id'])
    ).fetchone()
    
    return ProspectSettingResponse(
        id=new_prospect_setting._mapping['id'],
        name=new_prospect_setting._mapping['name'],
        company_description=new_prospect_setting._mapping.get('company_description'),
        industries=new_prospect_setting._mapping.get('industries'),
        locations=new_prospect_setting._mapping.get('locations'),
        employee_range=new_prospect_setting._mapping.get('employee_range'),
        revenue_range=new_prospect_setting._mapping.get('revenue_range'),
        title_keywords=new_prospect_setting._mapping.get('title_keywords'),
        seniority_levels=new_prospect_setting._mapping.get('seniority_levels'),
        buying_roles=new_prospect_setting._mapping.get('buying_roles'),
        hiring_roles=new_prospect_setting._mapping.get('hiring_roles'),
        new_hire_titles=new_prospect_setting._mapping.get('new_hire_titles'),
        funding_stages=new_prospect_setting._mapping.get('funding_stages'),
        tech_adoption=new_prospect_setting._mapping.get('tech_adoption'),
        ma_events=new_prospect_setting._mapping.get('ma_events'),
        exclusion_criteria=new_prospect_setting._mapping.get('exclusion_criteria'),
        created_at=new_prospect_setting._mapping['created_at'],
        updated_at=new_prospect_setting._mapping.get('updated_at')
    )
