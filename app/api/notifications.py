from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.notifications import NotificationCreate, NotificationRead, NotificationUpdate
from typing import List
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/notifications", tags=["notifications"], redirect_slashes=False)

@router.get("/", response_model=List[NotificationRead])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        notification_table = get_table('notifications', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(notification_table.select())
            notifications = result.fetchall()
        return [NotificationRead(**{k: notification._mapping[k] for k in notification._mapping.keys() if k in NotificationRead.__fields__}) for notification in notifications]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch notifications")

@router.post("/", response_model=NotificationRead)
def create_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        notification_table = get_table('notifications', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            notification_dict = notification_data.dict()
            notification_dict['id'] = uuid.uuid4()
            insert_stmt = notification_table.insert().values(**notification_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_notification = conn.execute(
                notification_table.select().where(notification_table.c.id == notification_dict['id'])
            ).fetchone()
        return NotificationRead(**{k: new_notification._mapping[k] for k in new_notification._mapping.keys() if k in NotificationRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create notification")

@router.put("/{notification_id}", response_model=NotificationRead)
def update_notification(
    notification_id: str,
    notification_data: NotificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        notification_table = get_table('notifications', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                notification_table.select().where(notification_table.c.id == notification_id)
            )
            notification = result.fetchone()
            if not notification:
                raise HTTPException(status_code=404, detail="Notification not found")
            
            update_data = {k: v for k, v in notification_data.dict().items() if v is not None}
            if update_data:
                update_stmt = notification_table.update().where(notification_table.c.id == notification_id).values(**update_data)
                conn.execute(update_stmt)
                conn.commit()
            
            updated_notification = conn.execute(
                notification_table.select().where(notification_table.c.id == notification_id)
            ).fetchone()
        return NotificationRead(**{k: updated_notification._mapping[k] for k in updated_notification._mapping.keys() if k in NotificationRead.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update notification")

@router.delete("/{notification_id}")
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        notification_table = get_table('notifications', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                notification_table.select().where(notification_table.c.id == notification_id)
            )
            notification = result.fetchone()
            if not notification:
                raise HTTPException(status_code=404, detail="Notification not found")
            delete_stmt = notification_table.delete().where(notification_table.c.id == notification_id)
            conn.execute(delete_stmt)
            conn.commit()
        return {"message": "Notification deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete notification") 