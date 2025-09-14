from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.users import User
from pydantic import BaseModel
from typing import Optional, List

try:
    from app.funnelprospects import (
        add_to_daily_list,
        remove_from_daily_list,
        update_daily_list_prospect_status,
        get_customer_prospects_list,
        update_has_replied_status
    )
    FUNNELPROSPECTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import funnelprospects: {e}")
    FUNNELPROSPECTS_AVAILABLE = False
    add_to_daily_list = None
    remove_from_daily_list = None
    update_daily_list_prospect_status = None
    get_customer_prospects_list = None
    update_has_replied_status = None

router = APIRouter(prefix="/daily-list", tags=["daily-list"])

class DailyListRequest(BaseModel):
    customer_id: str
    prospect_id_list: List[str]

class ProspectStatusRequest(BaseModel):
    customer_id: str
    prospect_id: str
    status: str
    activity_history: str

class HasRepliedRequest(BaseModel):
    customer_id: str
    prospect_id: str
    has_replied: bool
    activity_history: str = ""

@router.get("/")
def get_daily_list_endpoint(customer_id: str, prospect_profile_id: str = "default", limit: int = 100, offset: int = 0):
    if not FUNNELPROSPECTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        from app.funnelprospects import connect_db
        import json
        
        conn = connect_db()
        cur = conn.cursor()
        
        query = """
            SELECT 
                cp.prospect_id,
                cp.score,
                p.full_name,
                p.first_name,
                p.last_name,
                LEFT((p.vendordata->'experience'->1->>'company_name'),50) AS company_name,
                LEFT((p.vendordata->'experience'->1->>'position_title'),50) AS position_title,
                LEFT((p.vendordata->'experience'->1->>'department'),50) AS department,
                LEFT((p.vendordata->'experience'->1->>'management_level'),50) AS management_level,
                LEFT((p.vendordata->'experience'->1->>'company_type'),50) AS company_type,
                LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_5'),50) AS revenue_source_5,
                LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_1'),50) AS revenue_source_1,
                cp.activity_history,
                cp.status,
                cp.reply_content,
                cp.reply_sentiment,
                cp.created_at,
                cp.last_updated
            FROM customer_prospects cp
            JOIN prospects p ON cp.prospect_id = p.id
            WHERE cp.customer_id = %s 
                AND cp.prospect_profile_id = %s 
                AND cp.is_inside_daily_list = %s
            ORDER BY cp.created_at DESC
            LIMIT %s OFFSET %s
        """
        
        cur.execute(query, (customer_id, prospect_profile_id, True, limit, offset))
        results = cur.fetchall()
        
        count_query = """
            SELECT COUNT(*) 
            FROM customer_prospects 
            WHERE customer_id = %s AND prospect_profile_id = %s AND is_inside_daily_list = %s
        """
        cur.execute(count_query, (customer_id, prospect_profile_id, True))
        total_count = cur.fetchone()[0]
        
        cur.close()
        
        prospects = []
        for row in results:
            prospect_dict = {
                "prospect_id": row[0],
                "score": row[1],
                "full_name": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "company_name": row[5],
                "position_title": row[6],
                "department": row[7],
                "management_level": row[8],
                "company_type": row[9],
                "revenue_source_5": row[10],
                "revenue_source_1": row[11],
                "activity_history": row[12],
                "status": row[13],
                "reply_content": row[14],
                "reply_sentiment": row[15],
                "created_at": row[16].isoformat() if row[16] else None,
                "last_updated": row[17].isoformat() if row[17] else None,
            }
            prospects.append(prospect_dict)
        
        return {
            "status": "success",
            "message": f"Retrieved {len(prospects)} daily list prospects",
            "data": {
                "prospects": prospects,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(prospects)) < total_count
            }
        }
            
    except Exception as e:
        print(f"Error getting daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily list: {str(e)}"
        )

@router.post("/add-prospect")
def add_single_prospect_to_daily_list_endpoint(prospect_id: str, customer_id: str):
    if not FUNNELPROSPECTS_AVAILABLE or not add_to_daily_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = add_to_daily_list(
            customer_id=customer_id,
            prospect_id_list=[prospect_id]
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error adding prospect to daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add prospect to daily list: {str(e)}"
        )

@router.post("/remove-prospect")
def remove_single_prospect_from_daily_list_endpoint(prospect_id: str, customer_id: str):
    if not FUNNELPROSPECTS_AVAILABLE or not remove_from_daily_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = remove_from_daily_list(
            customer_id=customer_id,
            prospect_id_list=[prospect_id]
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error removing prospect from daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove prospect from daily list: {str(e)}"
        )

@router.post("/add")
def add_to_daily_list_endpoint(payload: DailyListRequest):
    if not FUNNELPROSPECTS_AVAILABLE or not add_to_daily_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = add_to_daily_list(
            customer_id=payload.customer_id,
            prospect_id_list=payload.prospect_id_list
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error adding to daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add to daily list: {str(e)}"
        )

@router.post("/remove")
def remove_from_daily_list_endpoint(payload: DailyListRequest):
    if not FUNNELPROSPECTS_AVAILABLE or not remove_from_daily_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = remove_from_daily_list(
            customer_id=payload.customer_id,
            prospect_id_list=payload.prospect_id_list
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error removing from daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove from daily list: {str(e)}"
        )

@router.put("/update-status")
def update_prospect_status_endpoint(payload: ProspectStatusRequest):
    if not FUNNELPROSPECTS_AVAILABLE or not update_daily_list_prospect_status:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = update_daily_list_prospect_status(
            customer_id=payload.customer_id,
            prospect_id=payload.prospect_id,
            status=payload.status,
            activity_history=payload.activity_history
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error updating prospect status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update prospect status: {str(e)}"
        )

@router.post("/reset")
def reset_daily_list_endpoint(customer_id: str):
    if not FUNNELPROSPECTS_AVAILABLE or not remove_from_daily_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        # Get all prospects that are in the daily list using direct database query
        from app.funnelprospects import connect_db
        
        conn = connect_db()
        cur = conn.cursor()
        
        # Get all prospect IDs that are in the daily list
        query = """
            SELECT prospect_id 
            FROM customer_prospects 
            WHERE customer_id = %s AND is_inside_daily_list = %s
        """
        cur.execute(query, (customer_id, True))
        results = cur.fetchall()
        cur.close()
        
        daily_list_prospect_ids = [row[0] for row in results]
        
        if not daily_list_prospect_ids:
            return {
                "status": "success",
                "message": "Daily list is already empty",
                "data": {
                    "removed_count": 0
                }
            }
        
        # Remove all prospects from daily list
        remove_result = remove_from_daily_list(
            customer_id=customer_id,
            prospect_id_list=daily_list_prospect_ids
        )
        
        if remove_result["status"] == "success":
            return {
                "status": "success",
                "message": f"Daily list reset successfully. Removed {remove_result['updated_count']} prospects.",
                "data": {
                    "removed_count": remove_result["updated_count"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=remove_result["message"]
            )
            
    except Exception as e:
        print(f"Error resetting daily list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset daily list: {str(e)}"
        )

@router.get("/available-prospects")
def get_available_prospects_endpoint(customer_id: str, prospect_profile_id: str = "default", show_thumbs_down: bool = False):
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer_prospects_list:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = get_customer_prospects_list(
            customer_id=customer_id,
            prospect_profile_id=prospect_profile_id,
            show_thumbs_down=show_thumbs_down
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": {
                    "prospects": result["prospect_list"],
                    "total_count": result["nb_prospects_returned"]
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error getting available prospects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available prospects: {str(e)}"
        )

@router.put("/update-reply-status")
def update_has_replied_status_endpoint(payload: HasRepliedRequest):
    if not FUNNELPROSPECTS_AVAILABLE or not update_has_replied_status:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = update_has_replied_status(
            customer_id=payload.customer_id,
            prospect_id=payload.prospect_id,
            has_replied=payload.has_replied,
            activity_history=payload.activity_history
        )
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error updating reply status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update reply status: {str(e)}"
        )
