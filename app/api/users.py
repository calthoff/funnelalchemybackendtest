from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.users import User
from app.schemas.users import UserRead, UserUpdate
from app.utils.auth import get_current_user
from app.utils.password import verify_password, hash_password
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/users", tags=["users"])

class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str

@router.get("/me", response_model=UserRead)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserRead.model_validate(current_user)

@router.put("/me", response_model=UserRead)
def update_current_user(
    profile_update: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    update_data = profile_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(current_user, field) and value is not None:
            setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return UserRead.model_validate(current_user)

@router.put("/me/password")
def update_password(
    password_update: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )
    hashed_new_password = hash_password(password_update.new_password)
    current_user.hashed_password = hashed_new_password
    db.commit()
    return {"message": "Password updated successfully"} 