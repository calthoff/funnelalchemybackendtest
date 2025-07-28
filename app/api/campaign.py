from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.db import get_db, engine
from sqlalchemy import text, Table, MetaData
from app.models.leads_temp import LeadTemp
from app.models.users import User
from app.utils.auth import get_current_user
from app.services.campaign import upload_leads_to_temp_with_scoring, check_duplicates_before_upload, process_midnight_batch
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.sql import select
from app.schemas.campaigns import CampaignDashboardStats, CampaignDashboardStatsPage
from app.services.instantly import get_instantly_api_key
from app.utils.db_utils import get_table

router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
    redirect_slashes=False
)

class LeadIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    name: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    revenue_range: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    funding_round: Optional[str] = None
    tech_stack: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    lead_score: Optional[int] = None
    personal_label: Optional[str] = None
    source_notes: Optional[str] = None
    personalization: Optional[dict] = None
    clay_enrichment: Optional[dict] = None
    enrichment_source: Optional[str] = None
    enriched_at: Optional[str] = None
    context: Optional[str] = None

class UploadLeadsRequest(BaseModel):
    new_leads: List[LeadIn]
    existing_leads: List[LeadIn]
    sdr_assignment_mode: str
    sdrs: Optional[List[str]]
    daily_push_limit: Optional[int]
    update_existing: Optional[bool] = False

class CheckDuplicatesRequest(BaseModel):
    leads: List[LeadIn]
    campaign_id: str

@router.post("/check-duplicates", response_model=dict)
async def check_duplicates_endpoint(
    payload: CheckDuplicatesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    duplicate_leads = await check_duplicates_before_upload(current_user.schema_name, db.bind, payload.leads, payload.campaign_id)
    return {
        "duplicates": duplicate_leads
    }

@router.post("/{campaign_id}/upload-leads", response_model=dict)
async def upload_leads_endpoint(
    campaign_id: str,
    payload: UploadLeadsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        new_leads = [lead.dict(exclude_unset=True) if hasattr(lead, 'dict') else lead for lead in getattr(payload, 'new_leads', [])]
        existing_leads = [lead.dict(exclude_unset=True) if hasattr(lead, 'dict') else lead for lead in getattr(payload, 'existing_leads', [])]
        api_key = await get_instantly_api_key(db, current_user)
        result = await upload_leads_to_temp_with_scoring(
            current_user.schema_name,
            db.bind,
            campaign_id,
            new_leads,
            existing_leads,
            payload.daily_push_limit,
            payload.sdr_assignment_mode,
            payload.sdrs,
            payload.update_existing,
            api_key=api_key
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateDuplicateLeadRequest(BaseModel):
    lead_id: str
    update_data: LeadIn

@router.post("/{campaign_id}/update-duplicate-lead", response_model=dict)
def update_duplicate_lead(
    campaign_id: str,
    payload: UpdateDuplicateLeadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        try:
            existing_lead = conn.execute(
                campaign_table.select().where(campaign_table.c.id == payload.lead_id)
            ).fetchone()
            if not existing_lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            for key, value in payload.update_data.dict(exclude_unset=True).items():
                if hasattr(existing_lead, key):
                    setattr(existing_lead, key, value)
            
            conn.execute(
                campaign_table.update()
                .where(campaign_table.c.id == payload.lead_id)
                .values(**{k: v for k, v in payload.update_data.dict(exclude_unset=True).items() if hasattr(existing_lead, k)})
            )
            conn.commit()
            return {
                "status": "success",
                "message": "Lead updated successfully",
                "lead": existing_lead
            }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/{campaign_id}/process-midnight-batch", response_model=dict)
async def process_midnight_batch_endpoint(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        try:
            result = await process_midnight_batch(conn, campaign_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}/update-daily-push-limit", response_model=dict)
def update_daily_push_limit(
    campaign_id: str,
    daily_push_limit: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        campaign_icp = conn.execute(
            campaign_table.select().where(campaign_table.c.id == campaign_id)
        ).fetchone()
        if not campaign_icp:
            return {"status": "error", "message": "Campaign ICP not found"}
        conn.execute(
            campaign_table.update()
            .where(campaign_table.c.id == campaign_id)
            .values(daily_push_limit=daily_push_limit)
        )
        conn.commit()
        return {"status": "success", "daily_push_limit": daily_push_limit}

@router.get("/{campaign_id}/check-leads-temp", response_model=dict)
async def check_leads_temp_endpoint(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        try:
            table_exists = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'leads_temp')"
            )).scalar()
            
            if not table_exists:
                LeadTemp.__table__.create(engine, checkfirst=True)
                return {"status": "created", "message": "leads_temp table created"}
            else:
                temp_count = conn.execute(
                    text(f"SELECT COUNT(*) FROM {LeadTemp.__tablename__} WHERE campaign_id = :campaign_id")
                ).params(campaign_id=campaign_id).scalar()
                return {"status": "exists", "temp_leads_count": temp_count}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/with-icp-info", response_model=List[Dict[str, Any]])
def get_campaigns_with_icp_info(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import logging
    import time
    logger = logging.getLogger("uvicorn")
    start_time = time.time()
    logger.info("[get_campaigns_with_icp_info] API call started.")

    get_time = time.time()
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    campaign_upload_mode_table = get_table('campaign_upload_mode', current_user.schema_name, db.bind)
    leads_temp_table = get_table('leads_temp', current_user.schema_name, db.bind)
    
    from sqlalchemy import case
    lead_counts_subq = (
        select(
            leads_temp_table.c.campaign_id.label('campaign_id'),
            func.count().label('total_leads'),
            func.count(case((leads_temp_table.c.pushed_status == 'pushed', 1))).label('pushed_leads')
        )
        .group_by(leads_temp_table.c.campaign_id)
        .subquery()
    )

    main_query = (
        select(
            *campaign_table.c,
            campaign_upload_mode_table.c.sdr_assignment_mode,
            campaign_upload_mode_table.c.daily_push_limit,
            lead_counts_subq.c.total_leads,
            lead_counts_subq.c.pushed_leads
        )
        .select_from(
            campaign_table
            .outerjoin(campaign_upload_mode_table, campaign_upload_mode_table.c.campaign_id == campaign_table.c.id)
            .outerjoin(lead_counts_subq, lead_counts_subq.c.campaign_id == campaign_table.c.id)
        )
        .order_by(campaign_table.c.created_at.desc())
    )

    with db.bind.connect() as conn:
        a = time.time()
        rows = conn.execute(main_query).fetchall()
        logger.info(f"{time.time() - a} , --------------------------------------------------")
        result = []
        for row in rows:
            campaign_data = dict(row._mapping)
            icp_info = {
                'sdr_assignment_mode': campaign_data.pop('sdr_assignment_mode', None),
                'daily_push_limit': campaign_data.pop('daily_push_limit', None)
            }
            campaign_data['icp_info'] = icp_info if any(icp_info.values()) else None
            campaign_data['pushed_leads'] = campaign_data.pop('pushed_leads', 0) or 0
            campaign_data['total_leads'] = campaign_data.pop('total_leads', 0) or 0
            result.append(campaign_data)
    elapsed = time.time() - start_time
    logger.info(f"[get_campaigns_with_icp_info] API call finished in {elapsed:.3f} seconds.")
    return result

@router.get("/dashboard", response_model=CampaignDashboardStatsPage)
def get_campaign_dashboard_stats(
    offset: int = 0,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    metadata = MetaData(schema=current_user.schema_name)
    campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
    campaign_upload_mode_table = get_table('campaign_upload_mode', current_user.schema_name, db.bind)
    leads_temp_table = get_table('leads_temp', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
    campaign_icps_table = get_table('campaign_icps', current_user.schema_name, db.bind)
    icps_table = get_table('icps', current_user.schema_name, db.bind)

    with db.bind.connect() as conn:
        campaigns = conn.execute(campaign_table.select()).fetchall()
        campaign_ids = [c.id for c in campaigns]

        campaign_icps = conn.execute(
            campaign_icps_table.select().where(campaign_icps_table.c.campaign_id.in_(campaign_ids))
        ).fetchall() if campaign_ids else []
        campaign_id_to_icp_ids = {}
        for cicp in campaign_icps:
            campaign_id_to_icp_ids.setdefault(cicp.campaign_id, []).append(cicp.icp_id)

        icp_ids = list({icp_id for icp_ids in campaign_id_to_icp_ids.values() for icp_id in icp_ids})
        icps = conn.execute(icps_table.select().where(icps_table.c.id.in_(icp_ids))).fetchall() if icp_ids else []
        icp_id_to_name = {icp.id: icp.name for icp in icps}

        leads_temp = conn.execute(
            leads_temp_table.select().where(leads_temp_table.c.campaign_id.in_(campaign_ids))
        ).fetchall() if campaign_ids else []
        campaign_id_to_leads_emailed = {}
        for lead in leads_temp:
            campaign_id_to_leads_emailed[lead.campaign_id] = campaign_id_to_leads_emailed.get(lead.campaign_id, 0) + 1

        campaign_leads = conn.execute(
            campaign_lead_table.select().where(campaign_lead_table.c.campaign_id.in_(campaign_ids))
        ).fetchall() if campaign_ids else []
        campaign_id_to_campaign_lead_ids = {}
        for cl in campaign_leads:
            campaign_id_to_campaign_lead_ids.setdefault(cl.campaign_id, []).append(cl.id)
        all_campaign_lead_ids = [cl.id for cl in campaign_leads]

        activities = conn.execute(
            lead_activity_table.select().where(lead_activity_table.c.campaign_lead_id.in_(all_campaign_lead_ids))
        ).fetchall() if all_campaign_lead_ids else []
        from collections import defaultdict
        campaign_lead_id_to_acts = defaultdict(list)
        for act in activities:
            campaign_lead_id_to_acts[act.campaign_lead_id].append(act)

        upload_modes = conn.execute(
            campaign_upload_mode_table.select().where(campaign_upload_mode_table.c.campaign_id.in_(campaign_ids))
        ).fetchall() if campaign_ids else []
        campaign_id_to_upload_mode = {um.campaign_id: um for um in upload_modes}

        results = []
        for campaign in campaigns:
            campaign_id = campaign.id
            campaign_name = campaign.name
            icp_names = [icp_id_to_name[icp_id] for icp_id in campaign_id_to_icp_ids.get(campaign_id, []) if icp_id in icp_id_to_name]
            leads_emailed = campaign_id_to_leads_emailed.get(campaign_id, 0)
            campaign_lead_ids = campaign_id_to_campaign_lead_ids.get(campaign_id, [])
            positive_replies = 0
            meetings_booked = 0
            deals_closed = 0
            for cl_id in campaign_lead_ids:
                for act in campaign_lead_id_to_acts.get(cl_id, []):
                    if act.type == 'replied' and act.description and 'positive' in act.description.lower():
                        positive_replies += 1
                    if act.type == 'meeting_booked':
                        meetings_booked += 1
                    if act.type == 'deal_won' or act.type == 'deal_lost':
                        deals_closed += 1
            mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
            company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
            with db.bind.connect() as sdr_conn:
                mapping_rows = sdr_conn.execute(
                    mapping_table.select().where(mapping_table.c.campaign_id == campaign_id)
                ).fetchall()
                company_ids = [m._mapping['campaign_company_id'] for m in mapping_rows]
                sdr_ids = []
                if company_ids:
                    assigned_sdrs = sdr_conn.execute(
                        company_table.select().where(
                            company_table.c.id.in_(company_ids),
                            company_table.c.assigned_sdr.isnot(None)
                        )
                    ).fetchall()
                    sdr_ids = [str(row._mapping['assigned_sdr']) for row in assigned_sdrs if row._mapping['assigned_sdr'] is not None]
                    sdr_ids = list(set(sdr_ids))
            results.append(CampaignDashboardStats(
                campaign_name=campaign_name,
                icp_used=icp_names,
                leads_emailed=leads_emailed,
                positive_replies=positive_replies,
                meetings_booked=meetings_booked,
                deals_closed=deals_closed,
                sdr_running=sdr_ids
            ))
        total = len(results)
        return {
            "items": results[offset:offset+limit],
            "total": total
        } 