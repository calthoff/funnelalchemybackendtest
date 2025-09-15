from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.users import User
from pydantic import BaseModel
from typing import Optional, List

try:
    from app.funnelprospects import (
        create_customer, 
        get_customer, 
        updateCustomerProspectCriteria,
        find_matching_prospects,
        findAndUpdateCustomerProspect,
        get_prospects_stats,
        add_to_daily_list,
        remove_from_daily_list,
        get_customer_prospect_criteria,
        get_customer_prospects_list,
        update_daily_list_prospect_status
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
    get_customer_prospect_criteria = None
    get_customer_prospects_list = None
    update_daily_list_prospect_status = None

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

class ProspectStatusRequest(BaseModel):
    customer_id: str
    prospect_id: str
    status: str
    activity_history: str

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
            
    except Exception as e:
        print(f"Error getting prospect stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospect stats: {str(e)}"
        )

@router.get("/{customer_id}")
def get_customer_info(customer_id: str):
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        print(f"Getting customer info for ID: {customer_id}")
        try:
            customer_id_int = int(customer_id)
            result = get_customer(customer_id_int)
        except ValueError:
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

@router.post("/{customer_id}/update-prospects")
def update_customer_prospects(customer_id: str, prospect_profile_id: str = "default", limit_prospects=500):
    if not FUNNELPROSPECTS_AVAILABLE or not findAndUpdateCustomerProspect:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = findAndUpdateCustomerProspect(customer_id, prospect_profile_id, limit_prospects = limit_prospects)
        
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

@router.get("/{customer_id}/prospects-status")
def get_prospect_matching_status(customer_id: str):
    """
    Get the status of prospect matching jobs for a customer.
    """
    try:
        from app.background_jobs import job_tracker
        
        # Get all jobs for this customer
        jobs = job_tracker.get_customer_jobs(customer_id)
        
        # Sort by started_at (most recent first)
        jobs.sort(key=lambda x: x["started_at"], reverse=True)
        
        return {
            "status": "success",
            "message": f"Found {len(jobs)} jobs for customer",
            "data": {
                "customer_id": customer_id,
                "jobs": jobs
            }
        }
        
    except Exception as e:
        print(f"Error getting prospect matching status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospect matching status: {str(e)}"
        )

@router.get("/job/{job_id}/status")
def get_job_status(job_id: str):
    """
    Get the status of a specific background job.
    """
    try:
        from app.background_jobs import job_tracker
        
        job = job_tracker.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )
        
        return {
            "status": "success",
            "message": "Job status retrieved",
            "data": job
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting job status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )

@router.get("/{customer_id}/get-prospect-criteria")
def get_customer_prospect_criteria_endpoint(customer_id: str, prospect_profile_id: str = "default"):
    if not FUNNELPROSPECTS_AVAILABLE or not get_customer_prospect_criteria:
        raise HTTPException(
            status_code=503,
            detail="AWS integration not available"
        )
    
    try:
        result = get_customer_prospect_criteria(customer_id, prospect_profile_id)
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "data": {
                    "customer_id": result["customer_id"],
                    "profile_id": result["profile_id"],
                    "criteria_dataset": result["criteria_dataset"]
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result["message"]
            )
            
    except Exception as e:
        print(f"Error getting prospect criteria: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prospect criteria: {str(e)}"
        )

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