from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.users import User
from pydantic import BaseModel
from typing import Optional, List

# Try to import funnelprospects, but handle gracefully if it fails
try:
    from app.funnelprospects import (
        create_customer, 
        get_customer, 
        updateCustomerProspectCriteria,
        find_matching_prospects,
        findAndUpdateCustomerProspect,
        get_prospects_stats,
        add_to_daily_list,
        remove_from_daily_list
    )
    FUNNELPROSPECTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import funnelprospects: {e}")
    FUNNELPROSPECTS_AVAILABLE = False
    create_customer = None
    get_customer = None
    updateCustomerProspectCriteria = None
    find_matching_prospects = None
    findAndUpdateCustomerProspect = None
    get_prospects_stats = None
    add_to_daily_list = None
    remove_from_daily_list = None

router = APIRouter(prefix="/customers", tags=["customers"])

class ProspectCriteriaRequest(BaseModel):
    customer_id: str
    prospect_profile_id: str
    company_industries: Optional[List[str]] = None
    company_employee_size_range: Optional[List[str]] = None
    company_revenue_range: Optional[List[str]] = None
    company_funding_stage: Optional[List[str]] = None
    company_location: Optional[List[str]] = None
    personas_title_keywords: Optional[List[str]] = None
    personas_seniority_levels: Optional[List[str]] = None
    personas_buying_roles: Optional[List[str]] = None
    company_description: str = ""
    company_exclusion_criteria: Optional[List[str]] = None

class DailyListRequest(BaseModel):
    customer_id: str
    prospect_id_list: List[str]

@router.get("/{customer_id}")
def get_customer_info(customer_id: str):
    """
    Get customer information from AWS database by customer_id
    """
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Getting customer info for ID: {customer_id}")
        # Try to convert to int first (for old integer customer IDs)
        try:
            customer_id_int = int(customer_id)
            result = get_customer(customer_id_int)
        except ValueError:
            # If it's not an integer, it might be a string customer ID
            # For now, we'll try to get customer info using the string ID
            # This might need to be adjusted based on the actual AWS API
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
            
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid customer ID format. Expected integer or string."
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting customer info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get customer information: {str(e)}"
        )

@router.post("/prospect-criteria")
def update_prospect_criteria(payload: ProspectCriteriaRequest):
    """
    Update prospect criteria for a customer in AWS database
    """
    if not FUNNELPROSPECTS_AVAILABLE or not updateCustomerProspectCriteria:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Updating prospect criteria for customer: {payload.customer_id}")
        result = updateCustomerProspectCriteria(
            customer_id=payload.customer_id,
            prospect_profile_id=payload.prospect_profile_id,
            company_industries=payload.company_industries,
            company_employee_size_range=payload.company_employee_size_range,
            company_revenue_range=payload.company_revenue_range,
            company_funding_stage=payload.company_funding_stage,
            company_location=payload.company_location,
            personas_title_keywords=payload.personas_title_keywords,
            personas_seniority_levels=payload.personas_seniority_levels,
            personas_buying_roles=payload.personas_buying_roles,
            company_description=payload.company_description,
            company_exclusion_criteria=payload.company_exclusion_criteria
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
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating prospect criteria: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update prospect criteria: {str(e)}"
        )

@router.get("/{customer_id}/matching-prospects")
def find_matching_prospects_for_customer(customer_id: str):
    """
    Find matching prospects for a customer based on their criteria
    """
    if not FUNNELPROSPECTS_AVAILABLE or not find_matching_prospects:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Finding matching prospects for customer: {customer_id}")
        result = find_matching_prospects(customer_id)
        
        return {
            "status": "success",
            "data": {
                "customer_id": customer_id,
                "matching_prospects": result
            }
        }
            
    except Exception as e:
        print(f"Error finding matching prospects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find matching prospects: {str(e)}"
        )

@router.post("/{customer_id}/update-prospects")
def update_customer_prospects(customer_id: str):
    """
    Find and update customer prospects
    """
    if not FUNNELPROSPECTS_AVAILABLE or not findAndUpdateCustomerProspect:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Updating prospects for customer: {customer_id}")
        result = findAndUpdateCustomerProspect(customer_id)
        
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
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating customer prospects: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update customer prospects: {str(e)}"
        )

@router.get("/stats")
def get_prospect_stats():
    """
    Get prospect statistics
    """
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
            
    except Exception as e:
        print(f"Error getting prospect stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospect stats: {str(e)}"
        )

@router.post("/daily-list/add")
def add_to_daily_list_endpoint(payload: DailyListRequest):
    """
    Add prospects to daily list
    """
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

@router.post("/daily-list/remove")
def remove_from_daily_list_endpoint(payload: DailyListRequest):
    """
    Remove prospects from daily list
    """
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