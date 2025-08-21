from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from uuid import UUID
import uuid
from datetime import datetime
import time

from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.daily_list import (
    DailyListCreate,
    DailyListUpdate,
    DailyListResponse
)
from app.utils.db_utils import get_table

router = APIRouter(prefix="/daily-list", tags=["daily-list"], redirect_slashes=False)

def create_prospect_activity(conn, prospect_id: str, activity_type: str, description: str, schema_name: str):
    try:
        print(f"Creating activity: prospect_id={prospect_id}, type={activity_type}, description={description}")
        prospect_activities_table = get_table('prospect_activities', schema_name, conn.engine)
        
        activity_data = {
            'id': str(uuid.uuid4()),
            'prospect_id': prospect_id,
            'type': activity_type,
            'source': 'daily_list',
            'description': description,
            'timestamp': datetime.utcnow()
        }
        
        insert_stmt = prospect_activities_table.insert().values(**activity_data)
        result = conn.execute(insert_stmt)
        
    except Exception as e:
        print(f"Error creating prospect activity: {e}")
        import traceback
        traceback.print_exc()

@router.get("/", response_model=List[DailyListResponse])
def get_daily_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        daily_list_table = get_table('daily_list', current_user.schema_name, db.bind)
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            result = conn.execute(
                daily_list_table.select()
                .where(daily_list_table.c.removed_date.is_(None))
                .order_by(daily_list_table.c.added_date.asc())
            )
            daily_list_items = result.fetchall()
            
            daily_list_with_prospects = []
            for item in daily_list_items:
                prospect_result = conn.execute(
                    prospect_table.select().where(prospect_table.c.id == item.prospect_id)
                )
                prospect = prospect_result.fetchone()
                
                if prospect:
                    item_dict = dict(item._mapping)
                    item_dict['prospect'] = dict(prospect._mapping)
                    daily_list_with_prospects.append(item_dict)
            
            return daily_list_with_prospects
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch daily list: {str(e)}")

@router.post("/add-prospect")
def add_prospect_to_daily_list(
    prospect_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        daily_list_table = get_table('daily_list', current_user.schema_name, db.bind)
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            prospect = conn.execute(
                prospect_table.select().where(prospect_table.c.id == prospect_id)
            ).fetchone()
            if not prospect:
                raise HTTPException(status_code=404, detail="Prospect not found")
            existing = conn.execute(
                daily_list_table.select().where(
                    (daily_list_table.c.prospect_id == prospect_id) &
                    (daily_list_table.c.removed_date.is_(None))
                )
            ).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Prospect already in daily list")
            
            daily_list_id = str(uuid.uuid4())
            current_time = datetime.utcnow()
            
            insert_data = {
                'id': daily_list_id,
                'prospect_id': prospect_id,
                'added_date': current_time,
                'contact_status': 'Not contacted',
                'is_primary': True,
                'daily_batch_date': current_time
            }
            insert_stmt = daily_list_table.insert().values(**insert_data)
            conn.execute(insert_stmt)
            conn.commit()
            return {"message": "Prospect added to daily list successfully", "daily_list_id": daily_list_id}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add prospect to daily list: {str(e)}")

@router.put("/{daily_list_id}")
def update_daily_list_item(
    daily_list_id: str,
    update_data: DailyListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a daily list item (contact status, notes, or remove)"""
    try:
        daily_list_table = get_table('daily_list', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            # Check if daily list item exists
            existing = conn.execute(
                daily_list_table.select().where(daily_list_table.c.id == daily_list_id)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Daily list item not found")
            
            # Prepare update data
            update_dict = update_data.dict(exclude_unset=True)
            
            # If contact status is being updated to 'Contacted' or 'Replied', remove from daily list
            if update_dict.get('contact_status') in ['Contacted', 'Replied']:
                update_dict['removed_date'] = datetime.utcnow()
                update_dict['removal_reason'] = update_dict.get('contact_status').lower()
                
                # Create activity entry
                activity_type = update_dict.get('contact_status').lower()
                description = f"Prospect {activity_type} and removed from Daily List"
                create_prospect_activity(
                    conn, 
                    str(existing.prospect_id), 
                    activity_type, 
                    description, 
                    current_user.schema_name
                )
            
            if update_dict:
                update_stmt = daily_list_table.update().where(
                    daily_list_table.c.id == daily_list_id
                ).values(**update_dict)
                conn.execute(update_stmt)
                conn.commit()
            
            return {"message": "Daily list item updated successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update daily list item: {str(e)}")

@router.post("/remove-prospect")
def remove_prospect_from_daily_list(
    daily_list_id: str,
    reason: str,  # 'not_a_fit', 'maybe_later', 'contacted', 'replied'
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a prospect from the daily list with a reason"""
    try:
        daily_list_table = get_table('daily_list', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            # Check if daily list item exists
            existing = conn.execute(
                daily_list_table.select().where(daily_list_table.c.id == daily_list_id)
            ).fetchone()
            
            if not existing:
                raise HTTPException(status_code=404, detail="Daily list item not found")
            
            # Create activity entry
            activity_type = reason
            description_map = {
                'not_a_fit': 'Prospect marked as Not a Fit and removed from Daily List',
                'maybe_later': 'Prospect marked as Maybe Later and removed from Daily List',
                'contacted': 'Prospect contacted and removed from Daily List',
                'replied': 'Prospect replied and removed from Daily List'
            }
            description = description_map.get(reason, f'Prospect removed from Daily List: {reason}')
            
            create_prospect_activity(
                conn, 
                str(existing.prospect_id), 
                activity_type, 
                description, 
                current_user.schema_name
            )
            
            # Remove from daily list
            update_stmt = daily_list_table.update().where(
                daily_list_table.c.id == daily_list_id
            ).values(
                removed_date=datetime.utcnow(),
                removal_reason=reason
            )
            conn.execute(update_stmt)
            conn.commit()
            
            return {"message": "Prospect removed from daily list successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove prospect from daily list: {str(e)}")

@router.post("/reset")
def reset_daily_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reset the daily list (remove all active prospects)"""
    try:
        daily_list_table = get_table('daily_list', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            # Get all active items before resetting
            active_items = conn.execute(
                daily_list_table.select().where(daily_list_table.c.removed_date.is_(None))
            ).fetchall()
            
            # Create activity entries for all active prospects
            for item in active_items:
                create_prospect_activity(
                    conn,
                    str(item.prospect_id),
                    'daily_reset',
                    'Daily List reset - prospect removed from active list',
                    current_user.schema_name
                )
            
            # Mark all active items as removed
            update_stmt = daily_list_table.update().where(
                daily_list_table.c.removed_date.is_(None)
            ).values(
                removed_date=datetime.utcnow(),
                removal_reason='daily_reset'
            )
            result = conn.execute(update_stmt)
            conn.commit()
            
            return {"message": f"Daily list reset successfully. {result.rowcount} prospects removed."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset daily list: {str(e)}") 