from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.personas import PersonaCreate, PersonaUpdate, PersonaRead
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/personas", tags=["personas"], redirect_slashes=False)

@router.get("/", response_model=List[PersonaRead])
def get_personas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(persona_table.select())
            personas = result.fetchall()
        return [PersonaRead(**{k: persona._mapping[k] for k in persona._mapping.keys() if k in PersonaRead.__fields__}) for persona in personas]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch personas")

@router.post("/", response_model=PersonaRead)
def create_persona(
    persona_data: PersonaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            persona_dict = persona_data.dict()
            persona_dict['id'] = uuid.uuid4()
            insert_stmt = persona_table.insert().values(**persona_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_persona = conn.execute(
                persona_table.select().where(persona_table.c.id == persona_dict['id'])
            ).fetchone()
        return PersonaRead(**{k: new_persona._mapping[k] for k in new_persona._mapping.keys() if k in PersonaRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create persona")

@router.get("/{persona_id}", response_model=PersonaRead)
def get_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                persona_table.select().where(persona_table.c.id == persona_id)
            )
            persona = result.fetchone()
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return PersonaRead(**{k: persona._mapping[k] for k in persona._mapping.keys() if k in PersonaRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch persona")

@router.put("/{persona_id}", response_model=PersonaRead)
def update_persona(
    persona_id: str,
    persona_data: PersonaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            update_data = {k: v for k, v in persona_data.dict().items() if v is not None}
            if update_data:
                update_stmt = persona_table.update().where(persona_table.c.id == persona_id).values(**update_data)
                result = conn.execute(update_stmt)
                conn.commit()
            updated_persona = conn.execute(
                persona_table.select().where(persona_table.c.id == persona_id)
            ).fetchone()
        if not updated_persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return PersonaRead(**{k: updated_persona._mapping[k] for k in updated_persona._mapping.keys() if k in PersonaRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update persona")

@router.delete("/{persona_id}")
def delete_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                persona_table.select().where(persona_table.c.id == persona_id)
            )
            persona = result.fetchone()
            if not persona:
                raise HTTPException(status_code=404, detail="Persona not found")
            delete_stmt = persona_table.delete().where(persona_table.c.id == persona_id)
            conn.execute(delete_stmt)
            conn.commit()
        return {"message": "Persona deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete persona") 