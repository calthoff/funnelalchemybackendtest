from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db
from app.models.users import User
from app.schemas.users import UserRead
from app.utils.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    with db.bind.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{current_user.schema_name}".users WHERE email = :email'),
            {"email": current_user.email}
        )
        user_data = result.fetchone()
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead(**{k: user_data._mapping[k] for k in user_data._mapping.keys() if k in UserRead.__fields__}) 