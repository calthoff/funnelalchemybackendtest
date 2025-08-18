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
    try:
        company_table = get_table('icps', current_user.schema_name, db.bind)
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            icps_result = conn.execute(company_table.select())
            icps = [dict(row._mapping) for row in icps_result.fetchall()]
            personas_result = conn.execute(persona_table.select())
            personas = [dict(row._mapping) for row in personas_result.fetchall()]
            company_description_result = conn.execute(company_description_table.select())
            company_description = company_description_result.fetchone()
            company_description_dict = dict(company_description._mapping) if company_description else {}
        
        if not icps and not personas:
            raise HTTPException(
                status_code=400, 
                detail="Please configure company profiles and personas before searching for prospects"
            )
        
        try:
            print(f"Searching for {limit} prospects")
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
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
    try:
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
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
    try:
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
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
    try:
        try:
            pdl_service = PDLService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="PDL API key not configured. Please set PDL_API_KEY environment variable."
            )
        
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            all_sdrs = conn.execute(sdr_table.select()).fetchall()
            
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
                existing_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.source_id == prospect_id)
                ).fetchone()
                
                if existing_prospect:
                    skipped_prospects.append(prospect_id)
                    continue
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