from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from sqlalchemy.exc import ProgrammingError
from app.db import get_db, Base, engine
from app.models.user_directory import UserDirectory
from app.schemas.companies import CompanyCreate, CompanyRead
from app.schemas.users import UserCreate
from app.utils.schema_utils import create_company_schema
import uuid
import jwt
import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from app.utils.email_utils import send_verification_email, send_reset_link_email
import random
from app.utils.password import hash_password, verify_password
from typing import List
from dotenv import load_dotenv
import secrets

router = APIRouter(prefix="/auth", tags=["auth"])
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

class SignupRequest(BaseModel):
    company: CompanyCreate
    user: UserCreate

class VerifyRequest(BaseModel):
    email: str
    code: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

def ensure_user_directory_table():
    inspector = inspect(engine)
    if not inspector.has_table('user_directory'):
        UserDirectory.__table__.create(engine, checkfirst=True)

@router.post("/signup", response_model=CompanyRead)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db)
):
    company = payload.company
    user = payload.user
    
    ensure_user_directory_table()
    
    try:
        existing_user = db.query(UserDirectory).filter_by(email=user.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please use a different email or login."
            )
    except ProgrammingError as e:
        if 'relation "user_directory" does not exist' in str(e):
            ensure_user_directory_table()
            existing_user = None
        else:
            raise
    
    schema_name = company.name.lower().replace(" ", "_") + "_" + str(uuid.uuid4())[:8]
    
    try:
        create_company_schema(db.get_bind(), schema_name)
        
        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.utcnow()
        
        verification_code = str(random.randint(100000, 999999))
        
        with engine.connect() as conn:  
            conn.execute(
                text(f'INSERT INTO "{schema_name}".companies (id, name, created_at, updated_at) VALUES (:id, :name, :created_at, :updated_at)'),
                {
                    "id": company_id,
                    "name": company.name,
                    "created_at": now,
                    "updated_at": now
                }
            )
            conn.execute(
                text(f'INSERT INTO "{schema_name}".users (id, first_name, last_name, email, role, approval_mode, hashed_password, is_verified, verification_code, created_at, updated_at) VALUES (:id, :first_name, :last_name, :email, :role, :approval_mode, :hashed_password, :is_verified, :verification_code, :created_at, :updated_at)'),
                {
                    "id": user_id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": "admin",
                    "approval_mode": "manual",
                    "hashed_password": hash_password(user.password),
                    "is_verified": False,
                    "verification_code": verification_code,
                    "created_at": now,
                    "updated_at": now
                }
            )
            conn.execute(
                text(f'INSERT INTO "{schema_name}".sdrs (id, name, role, territory, notes, status, created_at, updated_at) VALUES (:id, :name, :role, :territory, :notes, :status, :created_at, :updated_at)'),
                {
                    "id": str(uuid.uuid4()),
                    "name": f"{user.first_name} {user.last_name}",
                    "role": "",
                    "territory": "",
                    "notes": "",
                    "status": "active",
                    "created_at": now,
                    "updated_at": now
                }
            )
            conn.commit()
        
        db.execute(
            text('INSERT INTO public.user_directory (email, schema_name, company_name) VALUES (:email, :schema_name, :company_name)'),
            {
                "email": user.email,
                "schema_name": schema_name,
                "company_name": company.name
            }
        )
        db.commit()
        send_verification_email(user.email, verification_code)
        db.close()
        return CompanyRead(
            id=str(company_id),
            name=company.name,
            created_at=now,
            updated_at=now
        )
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    directory = db.query(UserDirectory).filter_by(email=email).first()
    if not directory:
        raise HTTPException(status_code=400, detail="User not found")
    schema_name = directory.schema_name
    with engine.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{schema_name}".users WHERE email = :email'),
            {"email": email}
        )
        user_data = result.fetchone()
    if not user_data or not verify_password(password, user_data.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if not user_data.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    access_token = create_access_token(data={"sub": user_data.email, "schema_name": schema_name})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/verify")
def verify_email(payload: VerifyRequest, db: Session = Depends(get_db)):
    email = payload.email
    code = payload.code
    
    directory = db.query(UserDirectory).filter_by(email=email).first()
    if not directory:
        raise HTTPException(status_code=404, detail="User not found")
    
    schema_name = directory.schema_name
    if not schema_name:
        raise HTTPException(status_code=500, detail="Schema name not found for user")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM "{schema_name}".users WHERE email = :email'),
                {"email": email}
            )
            user_data = result.fetchone()
            
            if not user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            if user_data.is_verified:
                access_token = create_access_token(data={"sub": email, "schema_name": schema_name})
                return {"access_token": access_token, "token_type": "bearer"}
            
            stored_code = str(user_data.verification_code) if user_data.verification_code else ""
            provided_code = str(code) if code else ""
            
            if stored_code != provided_code:
                raise HTTPException(status_code=400, detail="Invalid verification code")
            
            conn.execute(
                text(f'UPDATE "{schema_name}".users SET is_verified = true, verification_code = NULL, updated_at = NOW() WHERE email = :email'),
                {"email": email}
            )
            conn.commit()
            
            access_token = create_access_token(data={"sub": email, "schema_name": schema_name})
            return {"access_token": access_token, "token_type": "bearer"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    directory = db.query(UserDirectory).filter_by(email=payload.email).first()
    if not directory:
        raise HTTPException(status_code=404, detail="User not found")
    schema_name = directory.schema_name
    with engine.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{schema_name}".users WHERE email = :email'),
            {"email": payload.email}
        )
        user_data = result.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        token = secrets.token_urlsafe(32)
        conn.execute(
            text(f'UPDATE "{schema_name}".users SET reset_token = :token, reset_token_expires = :expires WHERE email = :email'),
            {
                "token": token,
                "expires": datetime.now(timezone.utc) + timedelta(hours=1),
                "email": payload.email
            }
        )
        conn.commit()
    reset_link = f"https://funnel-alchemy-production.up.railway.app/reset-password?token={token}"
    send_reset_link_email(user_data.email, reset_link)
    return {"message": "Password reset link sent"}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    from sqlalchemy import Table, MetaData, select, update
    from datetime import datetime, timezone
    directory_table = Table('user_directory', MetaData(schema='public'), autoload_with=db.bind)
    with db.bind.connect() as conn:
        schemas = conn.execute(select(directory_table.c.schema_name)).fetchall()
        schema_name = None
        user_email = None
        for row in schemas:
            schema = row._mapping['schema_name']
            user_table_schema = Table('users', MetaData(schema=schema), autoload_with=db.bind)
            user_row = conn.execute(select(user_table_schema).where(user_table_schema.c.reset_token == payload.token)).fetchone()
            if user_row:
                schema_name = schema
                user_email = user_row._mapping['email']
                break
        if not schema_name or not user_email:
            raise HTTPException(status_code=404, detail="User not found")
        user_table_schema = Table('users', MetaData(schema=schema_name), autoload_with=db.bind)
        user_row = conn.execute(select(user_table_schema).where(user_table_schema.c.reset_token == payload.token)).fetchone()
        if not user_row or not user_row._mapping['reset_token_expires'] or datetime.now(timezone.utc) > user_row._mapping['reset_token_expires']:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        conn.execute(update(user_table_schema)
            .where(user_table_schema.c.reset_token == payload.token)
            .values(
                hashed_password=hash_password(payload.new_password),
                reset_token=None,
                reset_token_expires=None
            )
        )
        conn.commit()
    return {"message": "Password reset successful"} 