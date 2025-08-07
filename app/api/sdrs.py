from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.sdrs import SDRCreate, SDRUpdate, SDR as SDRSchema, SDRDashboardStats, SDRDashboardStatsPage
from app.utils.file_utils import save_headshot_image, delete_headshot_image
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/sdrs", tags=["sdrs"], redirect_slashes=False)

@router.post("/upload-headshot")
async def upload_headshot(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload headshot image for SDR"""
    try:
        filename, url = await save_headshot_image(file)
        return {
            "filename": filename,
            "url": url,
            "message": "Headshot uploaded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upload headshot")

@router.get("/", response_model=List[SDRSchema])
def get_sdrs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select())
            sdrs = result.fetchall()
        return [SDRSchema(**{k: sdr._mapping[k] for k in sdr._mapping.keys() if k in SDRSchema.__fields__}) for sdr in sdrs]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch SDRs")

@router.post("/", response_model=SDRSchema)
def create_sdr(
    sdr_data: SDRCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            sdr_dict = sdr_data.dict()
            sdr_dict['id'] = uuid.uuid4()
            sdr_dict['status'] = 'active'
            
            # Filter out None values but allow empty strings for headshot fields
            existing_columns = [col.name for col in sdr_table.columns]
            filtered_dict = {}
            for k, v in sdr_dict.items():
                if k in existing_columns:
                    if k in ['headshot_url', 'headshot_filename']:
                        # Allow empty strings for headshot fields
                        filtered_dict[k] = v
                    elif v is not None:
                        # For other fields, only include non-None values
                        filtered_dict[k] = v
            
            print(f"Original data: {sdr_dict}")
            print(f"Filtered data: {filtered_dict}")
            print(f"Existing columns: {existing_columns}")
            
            insert_stmt = sdr_table.insert().values(**filtered_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.id == sdr_dict['id'])
            ).fetchone()
        return SDRSchema(**{k: new_sdr._mapping[k] for k in new_sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create SDR: {str(e)}")

@router.get("/{sdr_id}", response_model=SDRSchema)
def get_sdr(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
        return SDRSchema(**{k: sdr._mapping[k] for k in sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch SDR")

@router.put("/{sdr_id}", response_model=SDRSchema)
def update_sdr(
    sdr_id: str,
    sdr_data: SDRUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            
            # Check if we're updating the headshot
            old_headshot_filename = sdr._mapping.get('headshot_filename')
            new_headshot_filename = sdr_data.headshot_filename
            
            existing_columns = [col.name for col in sdr_table.columns]
            update_data = {}
            for k, v in sdr_data.dict(exclude_unset=True).items():
                if k in existing_columns:
                    if k in ['headshot_url', 'headshot_filename']:
                        update_data[k] = v
                    elif v is not None:
                        update_data[k] = v
            
            if update_data:
                # Delete old headshot if we're updating to a new one
                if (old_headshot_filename and 
                    new_headshot_filename and 
                    old_headshot_filename != new_headshot_filename):
                    delete_headshot_image(old_headshot_filename)
                
                update_stmt = sdr_table.update().where(sdr_table.c.id == sdr_id).values(**update_data)
                result = conn.execute(update_stmt)
                conn.commit()
            
            updated_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.id == sdr_id)
            ).fetchone()
        return SDRSchema(**{k: updated_sdr._mapping[k] for k in updated_sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update SDR: {str(e)}")

@router.delete("/{sdr_id}")
def delete_sdr(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            
            headshot_filename = sdr._mapping.get('headshot_filename')
            if headshot_filename:
                try:
                    delete_headshot_image(headshot_filename)
                except Exception as e:
                    print(f"Warning: Failed to delete headshot file {headshot_filename}: {e}")
            delete_stmt = sdr_table.delete().where(sdr_table.c.id == sdr_id)
            result = conn.execute(delete_stmt)
            conn.commit()
            
        return {"message": "SDR deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting SDR: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete SDR: {str(e)}")

@router.post("/{sdr_id}/toggle-status")
def toggle_sdr_status(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            current_status = sdr._mapping['status']
            new_status = 'paused' if current_status == 'active' else 'active'
            sdr_data = {
                'status': new_status
            }
            update_stmt = sdr_table.update().where(sdr_table.c.id == sdr_id).values(**sdr_data)
            result = conn.execute(update_stmt)
            conn.commit()
            updated_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.id == sdr_id)
            ).fetchone()
        return {
            "message": f"SDR {new_status} successfully",
            "status": updated_sdr._mapping['status']
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to toggle SDR status")

@router.delete("/{sdr_id}/headshot")
def delete_sdr_headshot(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            
            headshot_filename = sdr._mapping.get('headshot_filename')
            if not headshot_filename:
                raise HTTPException(status_code=404, detail="No headshot found for this SDR")
        
            try:
                delete_headshot_image(headshot_filename)
            except Exception as e:
                print(f"Warning: Failed to delete headshot file {headshot_filename}: {e}")
            
            update_data = {
                'headshot_url': None,
                'headshot_filename': None
            }
            update_stmt = sdr_table.update().where(sdr_table.c.id == sdr_id).values(**update_data)
            conn.execute(update_stmt)
            conn.commit()
            
        return {"message": "Headshot deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting headshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete headshot: {str(e)}") 