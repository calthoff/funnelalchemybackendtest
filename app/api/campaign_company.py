from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy import MetaData, select, update, delete, func
from typing import List, Dict
from app.db import get_db
from app.schemas.campaign_companies import CampaignCompanyRead, CampaignCompanyUpdate, InfiniteBatchResponse
from app.models.users import User
from app.utils.auth import get_current_user
from app.schemas.leads import LeadRead
from uuid import UUID
import uuid
from pydantic import BaseModel
import httpx
from app.utils.email_utils import send_leads_awaiting_approval_email
from app.utils.db_utils import get_table

router = APIRouter(
    prefix="/campaign-companies",
    tags=["campaign_companies"],
    redirect_slashes=False,
)

def get_primary_lead_for_company_campaign(db, company_id, campaign_id, current_user):
    metadata = MetaData(schema=current_user.schema_name)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)

    with db.bind.connect() as conn:
        mapping_row = conn.execute(
            select(mapping_table.c.id).where(
                (mapping_table.c.campaign_company_id == company_id) &
                (mapping_table.c.campaign_id == campaign_id)
            )
        ).fetchone()
        if not mapping_row:
            return None
        mapping_id = mapping_row._mapping['id']
        company_leads = conn.execute(
            select(lead_table).where(lead_table.c.campaign_company_campaign_map_id == mapping_id)
        ).fetchall()
        if not company_leads:
            return None
        for lead_row in company_leads:
            lead_data = dict(lead_row._mapping)
            assoc_result = conn.execute(
                select(campaign_lead_table).where(
                    (campaign_lead_table.c.lead_id == lead_data['id']) &
                    (campaign_lead_table.c.campaign_id == campaign_id) &
                    (campaign_lead_table.c.is_primary == True)
                )
            ).fetchone()
            if assoc_result:
                return lead_data
    return None

@router.get("/{campaign_company_id}/leads", response_model=List[LeadRead])
def get_leads_for_campaign_company(
    campaign_company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metadata = MetaData(schema=current_user.schema_name)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        mapping_ids = conn.execute(
            select(mapping_table.c.id).where(mapping_table.c.campaign_company_id == campaign_company_id)
        ).fetchall()
        mapping_id_list = [row._mapping['id'] for row in mapping_ids]
        if not mapping_id_list:
            return []
        leads = conn.execute(
            lead_table.select().where(lead_table.c.campaign_company_campaign_map_id.in_(mapping_id_list))
        ).fetchall()
    return [LeadRead(**{k: lead[k] for k in lead.keys() if k in LeadRead.__fields__}) for lead in leads]

@router.delete("/{campaign_company_id}", status_code=status.HTTP_200_OK)
async def delete_campaign_company(
    campaign_company_id: str,
    campaign_id: UUID = Query(..., description="Campaign ID to identify which campaign's primary lead to remove from Instantly"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    process_table = get_table('companies_process', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)

    with db.bind.connect() as conn:
        mapping_row = conn.execute(
            select(mapping_table.c.id).where(
                (mapping_table.c.campaign_company_id == campaign_company_id) & 
                (mapping_table.c.campaign_id == campaign_id)
            )
        ).fetchone()
        
        if not mapping_row:
            raise HTTPException(status_code=404, detail="Company not found in this campaign")

    with db.bind.begin() as conn:
        mapping_ids_result = conn.execute(select(mapping_table.c.id).where(mapping_table.c.campaign_company_id == campaign_company_id)).fetchall()
        mapping_ids = [row._mapping['id'] for row in mapping_ids_result]
        
        lead_ids_result = conn.execute(select(lead_table.c.id).where(lead_table.c.campaign_company_campaign_map_id.in_(mapping_ids))).fetchall()
        lead_ids = [row._mapping['id'] for row in lead_ids_result]
        campaign_lead_ids_result = conn.execute(
            select(campaign_lead_table.c.id).where(campaign_lead_table.c.lead_id.in_(lead_ids))
        ).fetchall()
        campaign_lead_ids = [row._mapping['id'] for row in campaign_lead_ids_result]
        lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
        if campaign_lead_ids:
            conn.execute(delete(lead_activity_table).where(lead_activity_table.c.campaign_lead_id.in_(campaign_lead_ids)))
        if lead_ids:
            conn.execute(delete(lead_process_table).where(lead_process_table.c.lead_id.in_(lead_ids)))
            conn.execute(delete(campaign_lead_table).where(campaign_lead_table.c.lead_id.in_(lead_ids)))
        if mapping_ids:
            conn.execute(delete(process_table).where(process_table.c.campaign_company_campaign_map_id.in_(mapping_ids)))
        conn.execute(delete(lead_table).where(lead_table.c.campaign_company_campaign_map_id.in_(mapping_ids)))
        conn.execute(delete(mapping_table).where(mapping_table.c.campaign_company_id == campaign_company_id))
        conn.execute(delete(company_table).where(company_table.c.id == campaign_company_id))
    
    return {"message": "Company deleted successfully"}

@router.put("/{campaign_company_id}", response_model=CampaignCompanyRead)
async def update_campaign_company(
    campaign_company_id: UUID,
    company_update: CampaignCompanyUpdate,
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    process_table = get_table('companies_process', current_user.schema_name, db.bind)
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)

    with db.bind.begin() as conn:
        company_row = conn.execute(
            select(company_table).where(company_table.c.id == campaign_company_id)
        ).fetchone()
        if not company_row:
            raise HTTPException(status_code=404, detail="Company not found")
        company = dict(company_row._mapping)

        update_data = company_update.dict(exclude_unset=True)
        new_stage = update_data.pop('stage', None)
        new_assigned_sdr = update_data.get('assigned_sdr', None)
        old_assigned_sdr = company.get('assigned_sdr', None)

        if update_data:
            conn.execute(
                update(company_table).where(company_table.c.id == campaign_company_id).values(**update_data)
            )
            company_row = conn.execute(
                select(company_table).where(company_table.c.id == campaign_company_id)
            ).fetchone()
            company = dict(company_row._mapping)

        if new_assigned_sdr and new_assigned_sdr != old_assigned_sdr:
            sdr_row = conn.execute(select(sdr_table).where(sdr_table.c.id == new_assigned_sdr)).fetchone()
            if sdr_row and sdr_row._mapping['email']:
                leads_for_company = conn.execute(select(lead_table).where(lead_table.c.campaign_company_campaign_map_id.in_(
                    select(mapping_table.c.id).where(mapping_table.c.campaign_company_id == company['id'])
                ))).fetchall()
                leads_for_csv = []
                for l in leads_for_company:
                    mapping_row = conn.execute(select(mapping_table).where(
                        (mapping_table.c.campaign_company_id == company['id']) & (mapping_table.c.campaign_id == campaign_id)
                    )).fetchone()
                    if mapping_row:
                        process_row = conn.execute(select(process_table).where(
                            process_table.c.campaign_company_campaign_map_id == mapping_row._mapping['id']
                        )).fetchone()
                        if process_row and process_row._mapping['status'] == 'Contacted':
                            lead_dict = dict(l._mapping)
                            leads_for_csv.append(lead_dict)
                if leads_for_csv:
                    send_leads_awaiting_approval_email(
                        sdr_row._mapping['email'],
                        sdr_row._mapping['name'].split()[0] if sdr_row._mapping['name'] else "SDR",
                        leads_for_csv
                    )

        if new_stage:
            mapping_row = conn.execute(select(mapping_table).where(
                (mapping_table.c.campaign_company_id == campaign_company_id) & (mapping_table.c.campaign_id == campaign_id)
            )).fetchone()
            if not mapping_row:
                raise HTTPException(status_code=404, detail="Company is not associated with the given campaign context")
            process_row = conn.execute(select(process_table).where(
                process_table.c.campaign_company_campaign_map_id == mapping_row._mapping['id']
            )).fetchone()
            if process_row:
                conn.execute(update(process_table).where(
                    process_table.c.id == process_row._mapping['id']
                ).values(status=new_stage))
            else:
                from sqlalchemy import insert
                conn.execute(insert(process_table).values(
                    campaign_company_campaign_map_id=mapping_row._mapping['id'],
                    status=new_stage
                ))
            
            company['stage'] = new_stage

            if new_stage in ['Replied', 'Meeting Booked','Negotiation', 'Closed Sale', 'Bounced', 'Disqualified']:
                primary_lead = get_primary_lead_for_company_campaign(db, str(campaign_company_id), campaign_id, current_user)
                if primary_lead:
                    primary_lead_id = primary_lead.get('primary_lead', primary_lead).get('id')
                    if primary_lead_id:
                        existing_lead_process = conn.execute(
                            select(lead_process_table).where(lead_process_table.c.lead_id == primary_lead_id)
                        ).fetchone()
                        
                        if existing_lead_process:
                            conn.execute(
                                update(lead_process_table)
                                .where(lead_process_table.c.lead_id == primary_lead_id)
                                .values(status=new_stage)
                            )
                        else:
                            from sqlalchemy import insert
                            conn.execute(
                                insert(lead_process_table).values(
                                    id=uuid.uuid4(),
                                    lead_id=primary_lead_id,
                                    status=new_stage
                                )
                            )
        else:
            mapping_row = conn.execute(select(mapping_table).where(
                (mapping_table.c.campaign_company_id == campaign_company_id) & (mapping_table.c.campaign_id == campaign_id)
            )).fetchone()
            if mapping_row:
                process_row = conn.execute(select(process_table).where(
                    process_table.c.campaign_company_campaign_map_id == mapping_row._mapping['id']
                )).fetchone()
                if process_row:
                    company['stage'] = process_row._mapping['status']
                else:
                    company['stage'] = "Contacted"
            else:
                company['stage'] = "Contacted"

    return company

class SetPrimaryContactRequest(BaseModel):
    campaign_id: str
    lead_id: str
    is_recycling: bool
    company_id: str

@router.post("/instantly-status", response_model=List[Dict])
async def get_instantly_status_for_campaigns(
    campaign_ids: List[UUID] = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metadata = MetaData(schema=current_user.schema_name)
    api_info_table = get_table('api_info', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        result = conn.execute(api_info_table.select().where(api_info_table.c.api_type == "instantly"))
        api_info = result.fetchone()
    instantly_api_key = api_info._mapping["api_key"] if api_info else None
    if not instantly_api_key:
        raise HTTPException(status_code=400, detail="Instantly API key not configured for user.")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.instantly.ai/api/v2/campaigns",
                headers={"Authorization": f"Bearer {instantly_api_key}"},
                timeout=10.0
            )
            resp.raise_for_status()
            instantly_campaigns = resp.json().get("items", [])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Instantly campaigns: {str(e)}")

    instantly_campaign_map = {c.get("id"): c for c in instantly_campaigns}

    results = []
    for campaign_id in campaign_ids:
        campaign_id_str = str(campaign_id)
        campaign_info = instantly_campaign_map.get(campaign_id_str)
        if not campaign_info:
            results.append({
                "campaign_id": campaign_id_str,
                "instantly_status": None,
                "sequences_empty": None,
                "campaign_name": None,
                "error": "No Instantly campaign found for this campaign_id"
            })
            continue
        status = campaign_info.get("status")
        sequences = campaign_info.get("sequences", [])
        has_valid_sequence = False
        for seq in sequences:
            for step in seq.get("steps", []):
                for variant in step.get("variants", []):
                    subject = (variant.get("subject") or "").strip()
                    body = (variant.get("body") or "").strip()
                    if subject and body:
                        has_valid_sequence = True
                        break
                if has_valid_sequence:
                    break
            if has_valid_sequence:
                break
        results.append({
            "campaign_id": campaign_id_str,
            "instantly_status": status,
            "sequences_empty": not has_valid_sequence,
            "campaign_name": campaign_info.get("name"),
        })
    return results

class BulkAssignSdrRequest(BaseModel):
    company_ids: List[UUID]
    assigned_sdr: UUID
    campaign_id: UUID

@router.post("/bulk-assign-sdr", status_code=200)
def bulk_assign_sdr(
    request: BulkAssignSdrRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metadata = MetaData(schema=current_user.schema_name)
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    process_table = get_table('companies_process', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)

    with db.bind.begin() as conn:
        sdr_row = conn.execute(select(sdr_table).where(sdr_table.c.id == request.assigned_sdr)).fetchone()
        if not sdr_row or not sdr_row._mapping['email']:
            raise HTTPException(status_code=404, detail="SDR not found or missing email")
        updated_companies = []
        all_leads_for_csv = []
        for company_id in request.company_ids:
            company_row = conn.execute(select(company_table).where(company_table.c.id == company_id)).fetchone()
            if not company_row:
                continue
            old_assigned_sdr = company_row._mapping['assigned_sdr']
            if old_assigned_sdr == request.assigned_sdr:
                continue
            conn.execute(update(company_table).where(company_table.c.id == company_id).values(assigned_sdr=request.assigned_sdr))
            leads_for_company = conn.execute(select(lead_table).where(lead_table.c.campaign_company_campaign_map_id.in_(
                select(mapping_table.c.id).where(mapping_table.c.campaign_company_id == company_id)
            ))).fetchall()
            mapping_row = conn.execute(select(mapping_table).where(
                (mapping_table.c.campaign_company_id == company_id) & (mapping_table.c.campaign_id == request.campaign_id)
            )).fetchone()
            updated_companies.append(str(company_id))
    return {"updated_companies": updated_companies, "assigned_sdr": str(request.assigned_sdr)}

class BulkApproveCompaniesRequest(BaseModel):
    company_ids: List[UUID]
    campaign_id: UUID

# @router.post("/bulk-approve", status_code=200)
# async def bulk_approve_companies(
#     request: BulkApproveCompaniesRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     metadata = MetaData(schema=current_user.schema_name)
#     company_table = Table('campaign_companies', metadata, autoload_with=db.bind)
#     mapping_table = Table('campaign_company_campaign_map', metadata, autoload_with=db.bind)
#     process_table = Table('companies_process', metadata, autoload_with=db.bind)
#     lead_table = Table('leads', metadata, autoload_with=db.bind)
#     campaign_lead_table = Table('campaign_leads', metadata, autoload_with=db.bind)
#     lead_process_table = Table('lead_processes', metadata, autoload_with=db.bind)

#     api_key = await get_instantly_api_key(db, current_user)
#     if not api_key:
#         raise HTTPException(status_code=400, detail="Instantly.ai API key not configured")

#     approved_companies = []
#     failed_companies = []
    
#     company_primary_leads = []
#     company_leads_map = {}
#     with db.bind.begin() as conn:
#         for company_id in request.company_ids:
#             mapping_row = conn.execute(
#                 select(mapping_table.c.id).where(
#                     (mapping_table.c.campaign_company_id == company_id) &
#                     (mapping_table.c.campaign_id == request.campaign_id)
#                 )
#             ).fetchone()
#             if not mapping_row:
#                 failed_companies.append({
#                     "company_id": str(company_id),
#                     "error": "Company not found in this campaign"
#                 })
#                 continue
#             mapping_id = mapping_row._mapping['id']
#             company_leads = conn.execute(
#                 select(lead_table).where(lead_table.c.campaign_company_campaign_map_id == mapping_id)
#             ).fetchall()
#             if not company_leads:
#                 failed_companies.append({
#                     "company_id": str(company_id),
#                     "error": "No leads found"
#                 })
#                 continue
#             primary_lead = None
#             for lead_row in company_leads:
#                 lead_data = dict(lead_row._mapping)
#                 assoc_result = conn.execute(
#                     select(campaign_lead_table).where(
#                         (campaign_lead_table.c.lead_id == lead_data['id']) &
#                         (campaign_lead_table.c.campaign_id == request.campaign_id) &
#                         (campaign_lead_table.c.is_primary == True)
#                     )
#                 ).fetchone()
#                 if assoc_result:
#                     primary_lead = lead_data
#                     break
#             if not primary_lead:
#                 failed_companies.append({
#                     "company_id": str(company_id),
#                     "error": "No primary lead found"
#                 })
#                 continue
#             company_primary_leads.append((company_id, primary_lead['email'], primary_lead))
#             company_leads_map[company_id] = (mapping_id, primary_lead)

#     emails = [email for _, email, _ in company_primary_leads]
#     found_emails, batch_error = await check_leads_exist_in_instantly_batch(api_key, request.campaign_id, emails)
#     if batch_error:
#         for company_id, email, _ in company_primary_leads:
#             failed_companies.append({
#                 "company_id": str(company_id),
#                 "error": batch_error
#             })
#         return {
#             "approved_companies": approved_companies,
#             "failed_companies": failed_companies,
#             "total_approved": len(approved_companies),
#             "total_failed": len(failed_companies)
#         }
#     tasks = []
#     company_task_map = []
#     for company_id, email, primary_lead in company_primary_leads:
#         if email.lower() in found_emails:
#             failed_companies.append({
#                 "company_id": str(company_id),
#                 "error": "Leads already exist in Instantly"
#             })
#             continue
#         mapping_id, _ = company_leads_map[company_id]
#         tasks.append(process_company_approval_for_instantly(api_key, request.campaign_id, primary_lead))
#         company_task_map.append((company_id, mapping_id, primary_lead))

#     results = await asyncio.gather(*tasks, return_exceptions=True)
    
#     for idx, (company_id, mapping_id, primary_lead) in enumerate(company_task_map):
#         result = results[idx]
#         if isinstance(result, Exception) or not result.get("success", False):
#             failed_companies.append({
#                 "company_id": str(company_id),
#                 "error": getattr(result, "error", str(result))
#             })
#             continue
#         with db.bind.begin() as conn:
#             conn.execute(
#                 update(process_table)
#                 .where(process_table.c.campaign_company_campaign_map_id == mapping_id)
#                 .values(status="Contacted")
#             )
            
#             # Update primary lead status in lead_process table for "Contacted" stage
#             primary_lead_id = primary_lead.get('id')
#             if primary_lead_id:
#                 # Check if lead_process record exists
#                 existing_lead_process = conn.execute(
#                     select(lead_process_table).where(lead_process_table.c.lead_id == primary_lead_id)
#                 ).fetchone()
                
#                 if existing_lead_process:
#                     # Update existing record
#                     conn.execute(
#                         update(lead_process_table)
#                         .where(lead_process_table.c.lead_id == primary_lead_id)
#                         .values(status="Contacted")
#                     )
#                 else:
#                     # Create new record
#                     from sqlalchemy import insert
#                     conn.execute(
#                         insert(lead_process_table).values(
#                             id=uuid.uuid4(),
#                             lead_id=primary_lead_id,
#                             status="Contacted"
#                         )
#                     )
#         approved_companies.append(str(company_id))

#     return {
#         "approved_companies": approved_companies,
#         "failed_companies": failed_companies,
#         "total_approved": len(approved_companies),
#         "total_failed": len(failed_companies)
#     }

@router.post("/infinite-batch", response_model=InfiniteBatchResponse)
def get_campaign_companies_infinite_batch(
    campaign_id: UUID = Body(...),
    stages: List[str] = Body([]),
    offsets: Dict[str, int] = Body(...),
    limits: Dict[str, int] = Body(...),
    search: str = Body(""),
    icp: str = Body(""),
    sdr: str = Body(""),
    date_filter: str = Body(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    process_table = get_table('companies_process', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)

    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start_date = None
    end_date = None
    if date_filter == 'this_month':
        start_date = datetime(now.year, now.month, 1)
        end_date = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1) if now.month < 12 else datetime(now.year + 1, 1, 1) - timedelta(seconds=1)
    elif date_filter == 'last_month':
        if now.month == 1:
            start_date = datetime(now.year - 1, 12, 1)
            end_date = datetime(now.year, 1, 1) - timedelta(seconds=1)
        else:
            start_date = datetime(now.year, now.month - 1, 1)
            end_date = datetime(now.year, now.month, 1) - timedelta(seconds=1)
    elif date_filter == 'last_week':
        start_date = now - timedelta(days=7)
        end_date = now
    elif date_filter == 'this_year':
        start_date = datetime(now.year, 1, 1)
        end_date = datetime(now.year, 12, 31, 23, 59, 59)
    elif date_filter == 'last_year':
        start_date = datetime(now.year - 1, 1, 1)
        end_date = datetime(now.year - 1, 12, 31, 23, 59, 59)

    results = {}
    all_paged_company_ids = set()
    stage_company_ids_map = {}
    count_result = {}
    with db.bind.connect() as conn:
        for stage in stages:
            query = company_table.select()
            query = query.select_from(
                company_table.join(
                    mapping_table, company_table.c.id == mapping_table.c.campaign_company_id
                ).join(
                    process_table, process_table.c.campaign_company_campaign_map_id == mapping_table.c.id
                )
            ).where(
                mapping_table.c.campaign_id == campaign_id,
                process_table.c.status == stage
            )
            if sdr:
                query = query.where(company_table.c.assigned_sdr == sdr)
            if icp:
                lead_company_ids = conn.execute(
                    select(lead_table.c.campaign_company_campaign_map_id)
                    .where(lead_table.c.icp_id == icp)
                ).fetchall()
                icp_mapping_ids = [row._mapping['campaign_company_campaign_map_id'] for row in lead_company_ids]
                if icp_mapping_ids:
                    query = query.where(mapping_table.c.id.in_(icp_mapping_ids))
                else:
                    results[stage] = []
                    count_result[stage] = 0
                    continue
            if start_date and end_date:
                query = query.where(company_table.c.created_at >= start_date, company_table.c.created_at <= end_date)
            if search:
                query = query.where(company_table.c.name.ilike(f"%{search}%"))
            count_query = query.with_only_columns(func.count()).order_by(None)
            total_count = conn.execute(count_query).scalar()
            count_result[stage] = total_count
            offset = offsets.get(stage, 0)
            limit = limits.get(stage, 20)
            query = query.offset(offset).limit(limit)
            companies = conn.execute(query).fetchall()
            paged_company_ids = [row._mapping['id'] for row in companies]
            all_paged_company_ids.update(paged_company_ids)
            stage_company_ids_map[stage] = paged_company_ids
            results[stage] = []
        if not all_paged_company_ids:
            results['count'] = count_result
            return results
        mappings = conn.execute(
            mapping_table.select().where(
                mapping_table.c.campaign_company_id.in_(all_paged_company_ids),
                mapping_table.c.campaign_id == campaign_id
            )
        ).fetchall()
        mapping_ids = [m._mapping['id'] for m in mappings]
        companies_map = {row._mapping['id']: row for row in conn.execute(company_table.select().where(company_table.c.id.in_(all_paged_company_ids))).fetchall()}
        process_rows = conn.execute(
            process_table.select().where(process_table.c.campaign_company_campaign_map_id.in_(mapping_ids))
        ).fetchall()
        process_map = {p._mapping['campaign_company_campaign_map_id']: p for p in process_rows}
        leads = conn.execute(
            lead_table.select().where(lead_table.c.campaign_company_campaign_map_id.in_(mapping_ids))
        ).fetchall()
        lead_ids = [l._mapping['id'] for l in leads]
        leads_map = {}
        for l in leads:
            company_id = next((m._mapping['campaign_company_id'] for m in mappings if m._mapping['id'] == l._mapping['campaign_company_campaign_map_id']), None)
            if company_id:
                if company_id not in leads_map:
                    leads_map[company_id] = []
                leads_map[company_id].append(l)
        campaign_leads = conn.execute(
            campaign_lead_table.select().where(
                campaign_lead_table.c.lead_id.in_(lead_ids),
                campaign_lead_table.c.campaign_id == campaign_id
            )
        ).fetchall()
        campaign_lead_map = {cl._mapping['lead_id']: cl for cl in campaign_leads}
        lead_processes = conn.execute(
            lead_process_table.select().where(lead_process_table.c.lead_id.in_(lead_ids))
        ).fetchall()
        lead_process_map = {lp._mapping['lead_id']: lp for lp in lead_processes}
        campaign_lead_ids = [cl._mapping['id'] for cl in campaign_leads]
        activities = conn.execute(
            lead_activity_table.select().where(lead_activity_table.c.campaign_lead_id.in_(campaign_lead_ids))
        ).fetchall()
        activity_map = {}
        for a in activities:
            cid = a._mapping['campaign_lead_id']
            if cid not in activity_map:
                activity_map[cid] = []
            activity_map[cid].append({
                'id': str(a._mapping['id']),
                'type': a._mapping['type'],
                'description': a._mapping['description'],
                'source': a._mapping['source'],
                'timestamp': a._mapping['timestamp'].isoformat() if a._mapping['timestamp'] else None
            })

        for stage in stages:
            for company_id in stage_company_ids_map[stage]:
                company_row = companies_map.get(company_id)
                if not company_row:
                    continue
                company_dict = {k: company_row._mapping[k] for k in company_row._mapping.keys() if k in CampaignCompanyRead.__fields__}
                mapping = next((m for m in mappings if m._mapping['campaign_company_id'] == company_id and m._mapping['campaign_id'] == campaign_id), None)
                process_row = process_map.get(mapping._mapping['id']) if mapping else None
                company_dict["stage"] = process_row._mapping['status'] if process_row else stage
                company_dict["created_at"] = process_row._mapping['created_at'] if process_row else None
                company_dict["updated_at"] = process_row._mapping['updated_at'] if process_row else None
                company_dict["isTier1"] = mapping._mapping['is_tier1'] if mapping and 'is_tier1' in mapping._mapping else False
                company_dict["isCold"] = mapping._mapping['is_cold'] if mapping and 'is_cold' in mapping._mapping else False
                company_dict["company_score"] = mapping._mapping['company_score'] if mapping and 'company_score' in mapping._mapping else 0

                company_leads = []
                for l in leads_map.get(company_id, []):
                    lead_dict = {k: l._mapping[k] for k in LeadRead.__fields__ if k in l._mapping}
                    cl = campaign_lead_map.get(l._mapping['id'])
                    lead_dict["campaign_id"] = str(cl._mapping['campaign_id']) if cl else None
                    lead_dict["campaign_company_id"] = str(company_id)
                    lp = lead_process_map.get(l._mapping['id'])
                    if lp:
                        lead_dict["status"] = lp._mapping['status'] if lp._mapping['status'] else "no reply"
                        lead_dict["lastContacted"] = lp._mapping['last_updated_at'] if lp._mapping['last_updated_at'] else None
                        lead_dict["reply_text_array"] = lp._mapping['reply_text_array'] if lp._mapping['reply_text_array'] else []
                        lead_dict["reply_classification"] = lp._mapping['reply_classification'] if lp._mapping['reply_classification'] else ""
                    if cl and cl._mapping['id'] in activity_map:
                        lead_dict["activities"] = activity_map[cl._mapping['id']]
                    else:
                        lead_dict["activities"] = []
                    company_leads.append(lead_dict)
                company_dict["leads"] = company_leads
                results[stage].append(company_dict)
        results['count'] = count_result
        return results

@router.get("/infinite", response_model=List[CampaignCompanyRead])
def get_campaign_companies_infinite(
    campaign_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query(""),
    icp: str = Query(""),
    sdr: str = Query(""),
    date_filter: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        mappings = conn.execute(
            mapping_table.select().where(mapping_table.c.campaign_id == campaign_id)
        ).fetchall()
    if not mappings:
        return []
    company_ids = [m._mapping['campaign_company_id'] for m in mappings]
    mapping_ids = [m._mapping['id'] for m in mappings]
    filtered_company_ids = set(company_ids)
    if sdr:
        company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            sdr_company_ids = set([row._mapping['id'] for row in conn.execute(company_table.select().where(company_table.c.assigned_sdr == sdr)).fetchall()])
        filtered_company_ids &= sdr_company_ids
    if icp:
        lead_table = get_table('leads', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            icp_leads = conn.execute(lead_table.select().where(lead_table.c.icp_id == icp)).fetchall()
            icp_mapping_ids = [row._mapping['campaign_company_campaign_map_id'] for row in icp_leads if row._mapping['campaign_company_campaign_map_id']]
            if icp_mapping_ids:
                icp_company_ids = set([row._mapping['campaign_company_id'] for row in conn.execute(
                    mapping_table.select().where(mapping_table.c.id.in_(icp_mapping_ids))
                ).fetchall()])
            else:
                icp_company_ids = set()
        filtered_company_ids &= icp_company_ids
    if date_filter:
        from datetime import datetime, timedelta, date
        now = datetime.utcnow()
        start_date = None
        end_date = None
        if date_filter == 'this_month':
            start_date = datetime(now.year, now.month, 1)
            if now.month == 12:
                end_date = datetime(now.year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1)
        elif date_filter == 'last_month':
            if now.month == 1:
                start_date = datetime(now.year - 1, 12, 1)
                end_date = datetime(now.year, 1, 1) - timedelta(seconds=1)
            else:
                start_date = datetime(now.year, now.month - 1, 1)
                end_date = datetime(now.year, now.month, 1) - timedelta(seconds=1)
        elif date_filter == 'last_week':
            start_date = now - timedelta(days=7)
            end_date = now
        elif date_filter == 'this_year':
            start_date = datetime(now.year, 1, 1)
            end_date = datetime(now.year, 12, 31, 23, 59, 59)
        elif date_filter == 'last_year':
            start_date = datetime(now.year - 1, 1, 1)
            end_date = datetime(now.year - 1, 12, 31, 23, 59, 59)
        if start_date and end_date:
            company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
            with db.bind.connect() as conn:
                date_company_ids = set([row._mapping['id'] for row in conn.execute(
                    company_table.select().where(
                        company_table.c.created_at >= start_date,
                        company_table.c.created_at <= end_date
                    )
                ).fetchall()])
            filtered_company_ids &= date_company_ids
    
    if search:
        company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            search_company_ids = set([row._mapping['id'] for row in conn.execute(
                company_table.select().where(company_table.c.name.ilike(f"%{search}%"))
            ).fetchall()])
        filtered_company_ids &= search_company_ids
    if status:
        company_process_table = get_table('companies_process', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            process_rows = conn.execute(
                company_process_table.select().where(company_process_table.c.status == status)
            ).fetchall()
            mapping_ids = [row._mapping['campaign_company_campaign_map_id'] for row in process_rows]

        if mapping_ids:
            mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
            with db.bind.connect() as conn:
                mapping_rows = conn.execute(
                    mapping_table.select().where(mapping_table.c.id.in_(mapping_ids))
                ).fetchall()
                stage_company_ids = set([row._mapping['campaign_company_id'] for row in mapping_rows])
        else:
            stage_company_ids = set()

        filtered_company_ids &= stage_company_ids
    filtered_company_ids = list(filtered_company_ids)
    paged_company_ids = filtered_company_ids[offset:offset+limit]
    if not paged_company_ids:
        return []
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        companies = conn.execute(company_table.select().where(company_table.c.id.in_(paged_company_ids))).fetchall()
    companies_map = {c._mapping['id']: c for c in companies}
    companies_process_table = get_table('companies_process', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        processes = conn.execute(companies_process_table.select().where(companies_process_table.c.campaign_company_campaign_map_id.in_(mapping_ids))).fetchall()
    process_map = {p._mapping['campaign_company_campaign_map_id']: p for p in processes}
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        join_stmt = campaign_lead_table.join(
            lead_table,
            campaign_lead_table.c.lead_id == lead_table.c.id
        ).join(
            mapping_table,
            lead_table.c.campaign_company_campaign_map_id == mapping_table.c.id
        )
        select_stmt = (
            select(
                *[lead_table.c[k] for k in LeadRead.__fields__ if k in lead_table.c],
                campaign_lead_table.c.campaign_id,
                campaign_lead_table.c.id.label('campaign_lead_id'),
                mapping_table.c.campaign_company_id.label('company_id'),
            )
            .select_from(join_stmt)
            .where(campaign_lead_table.c.campaign_id == campaign_id)
            .where(mapping_table.c.campaign_company_id.in_(paged_company_ids))
        )
        leads_with_campaign_data = conn.execute(select_stmt).fetchall()
        lead_ids = [lead_row._mapping['id'] for lead_row in leads_with_campaign_data]
        if lead_ids:
            process_stmt = (
                select(lead_process_table)
                .where(lead_process_table.c.lead_id.in_(lead_ids))
                .order_by(lead_process_table.c.lead_id, lead_process_table.c.last_updated_at.desc())
            )
            process_results = conn.execute(process_stmt).fetchall()
            process_map_by_lead = {}
            for row in process_results:
                lead_id = row._mapping['lead_id']
                if lead_id not in process_map_by_lead:
                    process_map_by_lead[lead_id] = row
            
            campaign_lead_ids = [lead_row._mapping['campaign_lead_id'] for lead_row in leads_with_campaign_data if 'campaign_lead_id' in lead_row._mapping]
            if campaign_lead_ids:
                activity_stmt = (
                    select(lead_activity_table)
                    .where(lead_activity_table.c.campaign_lead_id.in_(campaign_lead_ids))
                    .order_by(lead_activity_table.c.timestamp.desc())
                )
                activity_results = conn.execute(activity_stmt).fetchall()
                activity_map_by_campaign_lead = {}
                for row in activity_results:
                    campaign_lead_id = row._mapping['campaign_lead_id']
                    if campaign_lead_id not in activity_map_by_campaign_lead:
                        activity_map_by_campaign_lead[campaign_lead_id] = []
                    activity_map_by_campaign_lead[campaign_lead_id].append({
                        'id': str(row._mapping['id']),
                        'type': row._mapping['type'],
                        'description': row._mapping['description'],
                        'source': row._mapping['source'],
                        'timestamp': row._mapping['timestamp'].isoformat() if row._mapping['timestamp'] else None
                    })
            else:
                activity_map_by_campaign_lead = {}
        else:
            process_map_by_lead = {}
            activity_map_by_campaign_lead = {}
    leads_map = {}
    for lead_row in leads_with_campaign_data:
        lead = lead_row._mapping
        cl_campaign_id = lead['campaign_id']
        company_id = lead['company_id']
        if company_id not in leads_map:
            leads_map[company_id] = []
        lead_dict = {k: lead[k] for k in LeadRead.__fields__ if k in lead}
        lead_dict["campaign_id"] = str(cl_campaign_id) if cl_campaign_id else None
        lead_dict["campaign_company_id"] = str(company_id) if company_id else None
        process_result = process_map_by_lead.get(lead['id'])
        if process_result:
            process_map = process_result._mapping
            lead_dict["status"] = process_map['status'] if process_map['status'] else "no reply"
            lead_dict["lastContacted"] = process_map['last_updated_at'] if process_map['last_updated_at'] else None
            lead_dict["reply_text_array"] = process_map['reply_text_array'] if process_map['reply_text_array'] else []
            lead_dict["reply_classification"] = process_map['reply_classification'] if process_map['reply_classification'] else ""
            
            # Add lead activities
            campaign_lead_id = lead.get('campaign_lead_id')
            if campaign_lead_id and campaign_lead_id in activity_map_by_campaign_lead:
                lead_dict["activities"] = activity_map_by_campaign_lead[campaign_lead_id]
            else:
                lead_dict["activities"] = []
        leads_map[company_id].append(lead_dict)
    companies_list = []
    for company_id in paged_company_ids:
        company_row = companies_map.get(company_id)
        if not company_row:
            continue
        company_dict = {k: company_row._mapping[k] for k in company_row._mapping.keys() if k in CampaignCompanyRead.__fields__}
        mapping = next((m for m in mappings if m._mapping['campaign_company_id'] == company_id), None)
        company_dict['company_score'] = mapping._mapping['company_score'] if mapping and 'company_score' in mapping._mapping else None
        process_row = process_map.get(mapping._mapping['id']) if mapping else None
        process_row = None
        for p in processes:
            if p._mapping['campaign_company_campaign_map_id'] == mapping._mapping['id']:
                process_row = p
                break
        company_dict["stage"] = process_row._mapping['status'] if process_row else "Contacted"
        company_dict["created_at"] = process_row._mapping['created_at']
        company_dict["updated_at"] = process_row._mapping['updated_at']
        company_dict["leads"] = leads_map.get(company_id, [])
        companies_list.append(company_dict)
    return companies_list

class BulkDeleteCompaniesRequest(BaseModel):
    company_ids: List[str]
    campaign_id: str

@router.post("/bulk-delete", status_code=200)
async def bulk_delete_campaign_companies(
    request: BulkDeleteCompaniesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    process_table = get_table('companies_process', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)

    company_ids = [uuid.UUID(cid) for cid in request.company_ids]
    campaign_id = uuid.UUID(request.campaign_id)

    with db.bind.connect() as conn:
        for company_id in company_ids:
            mapping_row = conn.execute(
                select(mapping_table.c.id).where(
                    (mapping_table.c.campaign_company_id == company_id) &
                    (mapping_table.c.campaign_id == campaign_id)
                )
            ).fetchone()
            if not mapping_row:
                continue

    deleted = []
    with db.bind.begin() as conn:
        for company_id in company_ids:
            mapping_rows = conn.execute(
                select(mapping_table.c.id).where(
                    mapping_table.c.campaign_company_id == company_id,
                    mapping_table.c.campaign_id == campaign_id
                )
            ).fetchall()
            mapping_ids = [row.id for row in mapping_rows]
            lead_rows = conn.execute(
                select(lead_table.c.id).where(
                    lead_table.c.campaign_company_campaign_map_id.in_(mapping_ids)
                )
            ).fetchall()
            lead_ids = [row.id for row in lead_rows]
            campaign_lead_ids_result = conn.execute(
                select(campaign_lead_table.c.id).where(
                    campaign_lead_table.c.lead_id.in_(lead_ids),
                    campaign_lead_table.c.campaign_id == campaign_id
                )
            ).fetchall()
            campaign_lead_ids = [row.id for row in campaign_lead_ids_result]
            lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
            if campaign_lead_ids:
                conn.execute(delete(lead_activity_table).where(lead_activity_table.c.campaign_lead_id.in_(campaign_lead_ids)))
            if lead_ids:
                conn.execute(delete(lead_process_table).where(lead_process_table.c.lead_id.in_(lead_ids)))
                conn.execute(delete(campaign_lead_table).where(
                    campaign_lead_table.c.lead_id.in_(lead_ids),
                    campaign_lead_table.c.campaign_id == campaign_id
                ))
            if mapping_ids:
                conn.execute(delete(lead_table).where(lead_table.c.campaign_company_campaign_map_id.in_(mapping_ids)))
                conn.execute(delete(process_table).where(process_table.c.campaign_company_campaign_map_id.in_(mapping_ids)))
                conn.execute(delete(mapping_table).where(mapping_table.c.id.in_(mapping_ids)))
            # Only delete the company if there are no more mappings
            remaining_mappings = conn.execute(
                select(mapping_table.c.id).where(mapping_table.c.campaign_company_id == company_id)
            ).fetchall()
            if not remaining_mappings:
                conn.execute(delete(company_table).where(company_table.c.id == company_id))
            deleted.append(str(company_id))
    return {"deleted_company_ids": deleted, "message": f"Deleted {len(deleted)} companies."}

@router.put("/campaign-company-campaign-map/by-company-campaign")
async def update_mapping_by_company_campaign(
    company_id: UUID = Query(...),
    campaign_id: UUID = Query(...),
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    update_data = {}
    if 'isTier1' in data:
        update_data['is_tier1'] = data['isTier1']
    if 'isCold' in data:
        update_data['is_cold'] = data['isCold']
    with db.bind.begin() as conn:
        mapping_row = conn.execute(
            select(mapping_table).where(
                (mapping_table.c.campaign_company_id == company_id) &
                (mapping_table.c.campaign_id == campaign_id)
            )
        ).fetchone()
        if not mapping_row:
            raise HTTPException(status_code=404, detail="Mapping not found")
        conn.execute(
            update(mapping_table)
            .where(mapping_table.c.id == mapping_row._mapping['id'])
            .values(**update_data)
        )
        updated = conn.execute(
            select(mapping_table).where(mapping_table.c.id == mapping_row._mapping['id'])
        ).fetchone()
        result = dict(updated._mapping)
        return {
            **result,
            'isTier1': result.get('is_tier1', False),
            'isCold': result.get('is_cold', False)
        }