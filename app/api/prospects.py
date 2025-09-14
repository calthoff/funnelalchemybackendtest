from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.users import User
from pydantic import BaseModel
from typing import Optional, List

try:
    from app.funnelprospects import (
        get_customer_prospects_list,
        get_prospects_stats
    )
    FUNNELPROSPECTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import funnelprospects: {e}")
    FUNNELPROSPECTS_AVAILABLE = False
    get_customer_prospects_list = None
    get_prospects_stats = None

router = APIRouter(prefix="/prospects", tags=["prospects"])

@router.get("/")
def get_prospects(customer_id: Optional[str] = None, prospect_profile_id: str = "default", show_thumbs_down: bool = False):
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer_prospects_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="customer_id is required"
        )
    
    try:
        result = get_customer_prospects_list(
            customer_id=customer_id,
            prospect_profile_id=prospect_profile_id,
            show_thumbs_down=show_thumbs_down
        )
        
        if result["status"] == "success":
            return result["prospect_list"]
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting prospects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospects: {str(e)}"
        )

@router.get("/stats")
def get_prospect_stats():
    if not FUNNELPROSPECTS_AVAILABLE or not get_prospects_stats:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = get_prospects_stats()
        
        if result["status"] == "success":
            return {
                "status": "success",
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting prospect stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospect stats: {str(e)}"
        )
