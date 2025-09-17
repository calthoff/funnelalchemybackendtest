from fastapi import APIRouter, HTTPException, Depends
from app.models.users import User
from app.utils.auth import get_current_user
from pydantic import BaseModel
from typing import Optional, List
import json

try:
    from app.funnelprospects import get_contacted_list
    FUNNELPROSPECTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import funnelprospects: {e}")
    FUNNELPROSPECTS_AVAILABLE = False
    get_contacted_list = None

router = APIRouter(prefix="/contacted", tags=["contacted"])

class ContactedListRequest(BaseModel):
    customer_id: str
    prospect_profile_id: Optional[str] = "default"

@router.get("/list")
async def get_contacted_prospects_list(
    customer_id: str,
    prospect_profile_id: str = "default",
    current_user: User = Depends(get_current_user)
):
    """
    Get all contacted prospects for a customer
    """
    if not FUNNELPROSPECTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Funnelprospects service is not available"
        )
    
    try:
        # Call the funnelprospects function
        result = get_contacted_list(customer_id, prospect_profile_id)
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": "Contacted prospects retrieved successfully",
                "data": {
                    "prospects": result["prospect_list"],
                    "count": result["nb_prospects_returned"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Failed to retrieve contacted prospects")
            )
            
    except Exception as e:
        print(f"Error retrieving contacted prospects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve contacted prospects: {str(e)}"
        )
