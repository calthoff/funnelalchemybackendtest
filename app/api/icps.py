from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.icps import ICPCreate, ICPUpdate, ICPRead
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/icps", tags=["icps"], redirect_slashes=False)

@router.get("/", response_model=List[ICPRead])
def get_icps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        icp_table = get_table('icps', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(icp_table.select())
            icps = result.fetchall()
        return [ICPRead(**{k: icp._mapping[k] for k in icp._mapping.keys() if k in ICPRead.__fields__}) for icp in icps]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch ICPs")

@router.post("/", response_model=ICPRead)
def create_icp(
    icp_data: ICPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        icp_table = get_table('icps', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            icp_dict = icp_data.dict()
            icp_dict['id'] = uuid.uuid4()
            insert_stmt = icp_table.insert().values(**icp_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_icp = conn.execute(
                icp_table.select().where(icp_table.c.id == icp_dict['id'])
            ).fetchone()
        return ICPRead(**{k: new_icp._mapping[k] for k in new_icp._mapping.keys() if k in ICPRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create ICP")

@router.get("/{icp_id}", response_model=ICPRead)
def get_icp(
    icp_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        icp_table = get_table('icps', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                icp_table.select().where(icp_table.c.id == icp_id)
            )
            icp = result.fetchone()
        if not icp:
            raise HTTPException(status_code=404, detail="ICP not found")
        return ICPRead(**{k: icp._mapping[k] for k in icp._mapping.keys() if k in ICPRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch ICP")

@router.put("/{icp_id}", response_model=ICPRead)
def update_icp(
    icp_id: str,
    icp_data: ICPUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        icp_table = get_table('icps', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            update_data = {k: v for k, v in icp_data.dict().items() if v is not None}
            if update_data:
                update_stmt = icp_table.update().where(icp_table.c.id == icp_id).values(**update_data)
                result = conn.execute(update_stmt)
                conn.commit()
            updated_icp = conn.execute(
                icp_table.select().where(icp_table.c.id == icp_id)
            ).fetchone()
        if not updated_icp:
            raise HTTPException(status_code=404, detail="ICP not found")
        return ICPRead(**{k: updated_icp._mapping[k] for k in updated_icp._mapping.keys() if k in ICPRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update ICP")

@router.delete("/{icp_id}")
def delete_icp(
    icp_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        icp_table = get_table('icps', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                icp_table.select().where(icp_table.c.id == icp_id)
            )
            icp = result.fetchone()
            if not icp:
                raise HTTPException(status_code=404, detail="ICP not found")
            delete_stmt = icp_table.delete().where(icp_table.c.id == icp_id)
            conn.execute(delete_stmt)
            conn.commit()
        return {"message": "ICP deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete ICP") 