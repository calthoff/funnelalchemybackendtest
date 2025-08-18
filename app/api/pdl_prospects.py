from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.services.pdl_service import PDLService
from app.utils.db_utils import get_table
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pdl-prospects", tags=["pdl-prospects"], redirect_slashes=False)

@router.post("/search")
async def search_pdl_prospects(
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search for prospects using PDL API based on user's scoring settings
    """
    try:
        # Get user's scoring configuration
        company_table = get_table('icps', current_user.schema_name, db.bind)
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            # Get ICPs (company profiles)
            icps_result = conn.execute(company_table.select())
            icps = [dict(row._mapping) for row in icps_result.fetchall()]
            
            # Get personas
            personas_result = conn.execute(persona_table.select())
            personas = [dict(row._mapping) for row in personas_result.fetchall()]
            
            # Get company description
            company_description_result = conn.execute(company_description_table.select())
            company_description = company_description_result.fetchone()
            company_description_dict = dict(company_description._mapping) if company_description else {}
        
        # Check if user has configured scoring settings
        if not icps and not personas:
            raise HTTPException(
                status_code=400, 
                detail="Please configure company profiles and personas before searching for prospects"
            )
        
        # Initialize PDL service
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
        # Search for prospects
        prospects = await pdl_service.search_prospects(
            icps=icps,
            personas=personas,
            company_description=company_description_dict,
            limit=limit
        )
        
        return {
            "prospects": prospects,
            "total_found": len(prospects),
            "search_criteria": {
                "icps_count": len(icps),
                "personas_count": len(personas),
                "has_company_description": bool(company_description_dict)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching PDL prospects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search prospects: {str(e)}")

@router.post("/enrich")
async def enrich_prospect(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Enrich a single prospect using PDL API
    """
    try:
        # Initialize PDL service
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
        # Enrich prospect
        enriched_data = await pdl_service.enrich_prospect(email)
        
        if not enriched_data:
            raise HTTPException(status_code=404, detail="Prospect not found or could not be enriched")
        
        return enriched_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enriching prospect {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enrich prospect: {str(e)}")

@router.get("/company/{company_name}")
async def get_company_info(
    company_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get company information from PDL
    """
    try:
        # Initialize PDL service
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
        # Get company info
        company_info = pdl_service.get_company_info(company_name)
        
        if not company_info:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return company_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company info for {company_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get company info: {str(e)}")

@router.post("/import")
async def import_pdl_prospects(
    prospect_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import selected PDL prospects into the user's database
    """
    try:
        # Initialize PDL service
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
        # Get prospect table
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            # Get SDRs for assignment
            all_sdrs = conn.execute(sdr_table.select()).fetchall()
            
            # Get last prospect for round-robin assignment
            last_prospect = conn.execute(
                prospect_table.select().order_by(prospect_table.c.created_at.desc())
            ).fetchone()
        
        assigned_sdr_id = None
        if all_sdrs:
            if last_prospect and last_prospect.sales_rep_id:
                last_sdr_index = next((i for i, sdr in enumerate(all_sdrs) 
                                     if str(sdr.id) == str(last_prospect.sales_rep_id)), -1)
                next_sdr_index = (last_sdr_index + 1) % len(all_sdrs)
                assigned_sdr_id = str(all_sdrs[next_sdr_index].id)
            else:
                assigned_sdr_id = str(all_sdrs[0].id)
        
        imported_prospects = []
        skipped_prospects = []
        
        for prospect_id in prospect_ids:
            try:
                # Get prospect details from PDL (you might need to store this data temporarily)
                # For now, we'll assume the prospect data is passed in the request
                # In a real implementation, you'd need to store the search results temporarily
                
                # Check if prospect already exists
                existing_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.source_id == prospect_id)
                ).fetchone()
                
                if existing_prospect:
                    skipped_prospects.append(prospect_id)
                    continue
                
                # Import prospect (you'd need the actual prospect data here)
                # This is a placeholder - you'd need to implement the actual import logic
                
            except Exception as e:
                logger.error(f"Error importing prospect {prospect_id}: {str(e)}")
                skipped_prospects.append(prospect_id)
        
        return {
            "imported": len(imported_prospects),
            "skipped": len(skipped_prospects),
            "imported_prospects": imported_prospects,
            "skipped_prospect_ids": skipped_prospects
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing PDL prospects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import prospects: {str(e)}") 