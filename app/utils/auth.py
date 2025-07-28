from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db
from app.models.users import User
import os
import time

bearer_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)):
    print("get_current_user CALLED")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        print("Decoding JWT...")
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        user_email: str = payload.get("sub")
        schema_name: str = payload.get("schema_name")
        print(f"JWT decoded: user_email={user_email}, schema_name={schema_name}")
    except JWTError as e:
        print("JWTError:", e)
        raise credentials_exception
    try:
        with db.bind.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM "{schema_name}".users WHERE email = :email'),
                {"email": user_email}
            )
            user_data = result.fetchone()
        if user_data is None:
            print("User not found in DB")
            raise credentials_exception
        class UserObj:
            pass
        user = UserObj()
        for key in user_data._mapping.keys():
            setattr(user, key, user_data._mapping[key])
        user.schema_name = schema_name
        return user
    except Exception as e:
        print(f"Database query error: {e}")
        if "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database schema not found. Please contact support."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        ) 