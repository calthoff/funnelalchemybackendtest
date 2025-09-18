from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db, engine
from app.models.users import User
from app.schemas.users import UserCreate, UserRead
import uuid
import jwt
import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import Optional
from app.utils.email_utils import send_verification_email, send_reset_link_email
import random
from app.utils.password import hash_password, verify_password
from dotenv import load_dotenv
import secrets

# Try to import funnelprospects, but handle gracefully if it fails
try:
    from app.funnelprospects import create_customer
    FUNNELPROSPECTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import funnelprospects: {e}")
    FUNNELPROSPECTS_AVAILABLE = False
    create_customer = None

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

class CompanyCreate(BaseModel):
    name: str

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    role: Optional[str] = "admin"
    approval_mode: Optional[str] = "manual"

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

@router.post("/signup", response_model=UserRead)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db)
):
    print(f"Received signup request - email: {payload.user.email}, company: {payload.company.name}")
    
    # Check if user already exists
    existing_user = db.query(User).filter_by(email=payload.user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered. Please use a different email or login."
        )
    
    # Create new user
    user_id = uuid.uuid4()
    verification_code = str(random.randint(100000, 999999))
    
    new_user = User(
        id=user_id,
        role=payload.user.role,
        first_name=payload.user.first_name,
        last_name=payload.user.last_name,
        email=payload.user.email,
        hashed_password=hash_password(payload.user.password),
        approval_mode=payload.user.approval_mode,
        is_verified=False,
        verification_code=verification_code,
        company_name=payload.company.name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create customer in AWS database (if available)
    aws_customer_result = None
    if FUNNELPROSPECTS_AVAILABLE and create_customer:
        try:
            try:
                import app.funnelprospects as fp
                if hasattr(fp, '_aws_connection') and fp._aws_connection:
                    try:
                        fp._aws_connection.close()
                    except:
                        pass
                    fp._aws_connection = None
                    print("🔄 Reset AWS connection")
            except Exception as reset_error:
                print(f"⚠️ Could not reset connection: {reset_error}")
                pass
            
            aws_customer_result = create_customer(
                email_address=payload.user.email,
                first_name=payload.user.first_name,
                last_name=payload.user.last_name,
                company_name=payload.company.name
            )
            
            if aws_customer_result and aws_customer_result.get("status") == "success":
                new_user.aws_customer_id = str(aws_customer_result.get('customer_id'))
                db.commit()
            else:
                print(f"❌ AWS customer creation failed: {aws_customer_result.get('message', 'Unknown error') if aws_customer_result else 'No response'}")
                
        except Exception as e:
            print(f"❌ Error creating AWS customer: {str(e)}")
            # Don't fail the signup if AWS customer creation fails
            aws_customer_result = {
                "status": "error",
                "message": f"Failed to create AWS customer: {str(e)}"
            }
    else:
        print("⚠️ AWS funnelprospects not available - skipping AWS customer creation")
        aws_customer_result = {
            "status": "skipped",
            "message": "AWS integration not available"
        }
    
    # Send verification email
    try:
        send_verification_email(payload.user.email, verification_code)
    except Exception as e:
        print(f"Failed to send verification email: {e}")
    
    # Prepare response
    response_data = UserRead(
        id=new_user.id,
        role=new_user.role,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        email=new_user.email,
        approval_mode=new_user.approval_mode,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        company_name=new_user.company_name
    )
    
    if aws_customer_result and aws_customer_result["status"] == "success":
        response_data.aws_customer_id = str(aws_customer_result.get("customer_id"))
    
    return response_data

@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/verify")
def verify_email(payload: VerifyRequest, db: Session = Depends(get_db)):
    email = payload.email
    code = payload.code
    
    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        access_token = create_access_token(data={"sub": email})
        return {"access_token": access_token, "token_type": "bearer"}
    
    stored_code = str(user.verification_code) if user.verification_code else ""
    provided_code = str(code) if code else ""
    
    if stored_code != provided_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    user.is_verified = True
    user.verification_code = None
    user.updated_at = datetime.utcnow()
    db.commit()
    
    access_token = create_access_token(data={"sub": email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email).first()
    if not user:
        return {"message": "If the email exists, a password reset link has been sent"}
    
    reset_token = secrets.token_urlsafe(32)
    reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    
    user.reset_token = reset_token
    user.reset_token_expires = reset_token_expires
    db.commit()
    
    try:
        send_reset_link_email(payload.email, reset_token)
    except Exception as e:
        print(f"Failed to send reset email: {e}")
    
    return {"message": "If the email exists, a password reset link has been sent"}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(reset_token=payload.token).first()
    
    if not user or not user.reset_token_expires or datetime.utcnow() > user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Password reset successful"}
def get_customer_info(
    customer_id: int,
    db: Session = Depends(get_db)
):
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Getting customer info for ID: {customer_id}")
        result = get_customer(customer_id)
        
        if result["status"] == "success":
            return {
                "status": "success",
                "data": {
                    "customer_id": result["customer_id"],
                    "first_name": result["first_name"],
                    "last_name": result["last_name"],
                    "company_name": result["company_name"],
                    "email_address": result["email_address"],
                    "company_unique_id": result["company_unique_id"],
                    "prospect_profiles_ids": result["prospect_profiles_ids"]
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result["message"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting customer info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get customer information: {str(e)}"
        )