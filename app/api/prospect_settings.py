from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import uuid

from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.prospect_setting import (
    ProspectSettingCreate,
    ProspectSettingUpdate,
    ProspectSettingResponse
)
from app.utils.db_utils import get_table

router = APIRouter(prefix="/prospect-settings", tags=["prospect-settings"], redirect_slashes=False)

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
        return [ProspectSettingResponse(**{k: setting._mapping[k] for k in setting._mapping.keys() if k in ProspectSettingResponse.__fields__}) for setting in prospect_settings]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch prospect settings")

@router.get("/{prospect_setting_id}", response_model=ProspectSettingResponse)
def get_prospect_setting(
    prospect_setting_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_settings_table.select().where(prospect_settings_table.c.id == prospect_setting_id)
            )
            prospect_setting = result.fetchone()
            if not prospect_setting:
                raise HTTPException(status_code=404, detail="Prospect setting not found")
        return ProspectSettingResponse(**{k: prospect_setting._mapping[k] for k in prospect_setting._mapping.keys() if k in ProspectSettingResponse.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch prospect setting")

@router.post("/", response_model=ProspectSettingResponse)
def create_prospect_setting(
    prospect_setting_data: ProspectSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            prospect_setting_dict = prospect_setting_data.dict()
            prospect_setting_dict['id'] = uuid.uuid4()
            insert_stmt = prospect_settings_table.insert().values(**prospect_setting_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_prospect_setting = conn.execute(
                prospect_settings_table.select().where(prospect_settings_table.c.id == prospect_setting_dict['id'])
            ).fetchone()
        return ProspectSettingResponse(**{k: new_prospect_setting._mapping[k] for k in new_prospect_setting._mapping.keys() if k in ProspectSettingResponse.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create prospect setting")

@router.put("/{prospect_setting_id}", response_model=ProspectSettingResponse)
def update_prospect_setting(
    prospect_setting_id: str,
    prospect_setting_data: ProspectSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_settings_table.select().where(prospect_settings_table.c.id == prospect_setting_id)
            )
            prospect_setting = result.fetchone()
            if not prospect_setting:
                raise HTTPException(status_code=404, detail="Prospect setting not found")
            
            update_data = {k: v for k, v in prospect_setting_data.dict().items() if v is not None}
            if update_data:
                update_stmt = prospect_settings_table.update().where(prospect_settings_table.c.id == prospect_setting_id).values(**update_data)
                conn.execute(update_stmt)
                conn.commit()
            
            updated_prospect_setting = conn.execute(
                prospect_settings_table.select().where(prospect_settings_table.c.id == prospect_setting_id)
            ).fetchone()
        return ProspectSettingResponse(**{k: updated_prospect_setting._mapping[k] for k in updated_prospect_setting._mapping.keys() if k in ProspectSettingResponse.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update prospect setting")

@router.delete("/{prospect_setting_id}")
def delete_prospect_setting(
    prospect_setting_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        prospect_settings_table = get_table('prospect_settings', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                prospect_settings_table.select().where(prospect_settings_table.c.id == prospect_setting_id)
            )
            prospect_setting = result.fetchone()
            if not prospect_setting:
                raise HTTPException(status_code=404, detail="Prospect setting not found")
            delete_stmt = prospect_settings_table.delete().where(prospect_settings_table.c.id == prospect_setting_id)
            conn.execute(delete_stmt)
            conn.commit()
        return {"message": "Prospect setting deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete prospect setting") 