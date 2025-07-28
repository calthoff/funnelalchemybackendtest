from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.schemas.sdrs import SDRCreate, SDRUpdate, SDR as SDRSchema, SDRDashboardStats, SDRDashboardStatsPage
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/sdrs", tags=["sdrs"], redirect_slashes=False)

@router.get("/", response_model=List[SDRSchema])
def get_sdrs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select())
            sdrs = result.fetchall()
        return [SDRSchema(**{k: sdr._mapping[k] for k in sdr._mapping.keys() if k in SDRSchema.__fields__}) for sdr in sdrs]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch SDRs")

@router.post("/", response_model=SDRSchema)
def create_sdr(
    sdr_data: SDRCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(
                sdr_table.select().where(sdr_table.c.email == sdr_data.email)
            )
            existing_sdr = result.fetchone()
            if existing_sdr:
                raise HTTPException(status_code=400, detail="SDR with this email already exists")
            sdr_dict = sdr_data.dict()
            sdr_dict['id'] = uuid.uuid4()
            insert_stmt = sdr_table.insert().values(**sdr_dict)
            result = conn.execute(insert_stmt)
            conn.commit()
            new_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.email == sdr_data.email)
            ).fetchone()
        return SDRSchema(**{k: new_sdr._mapping[k] for k in new_sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create SDR")

@router.get("/dashboard", response_model=SDRDashboardStatsPage)
def get_sdr_dashboard_stats(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
    campaign_company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    mapping_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)

    with db.bind.connect() as conn:
        sdrs = conn.execute(sdr_table.select()).fetchall()
        sdr_ids = [s.id for s in sdrs]

        leads_emailed_rows = conn.execute(
            select(
                campaign_company_table.c.assigned_sdr,
                func.count(lead_table.c.id).label('leads_emailed')
            )
            .select_from(
                campaign_company_table
                .join(mapping_table, campaign_company_table.c.id == mapping_table.c.campaign_company_id)
                .join(lead_table, lead_table.c.campaign_company_campaign_map_id == mapping_table.c.id)
            )
            .where(campaign_company_table.c.assigned_sdr.in_(sdr_ids))
            .group_by(campaign_company_table.c.assigned_sdr)
        ).fetchall()
        leads_emailed_map = {row.assigned_sdr: row.leads_emailed for row in leads_emailed_rows}

        campaigns_touched_rows = conn.execute(
            select(
                campaign_company_table.c.assigned_sdr,
                func.count(func.distinct(campaign_lead_table.c.campaign_id)).label('campaigns_touched')
            )
            .select_from(
                campaign_company_table
                .join(mapping_table, campaign_company_table.c.id == mapping_table.c.campaign_company_id)
                .join(lead_table, lead_table.c.campaign_company_campaign_map_id == mapping_table.c.id)
                .join(campaign_lead_table, campaign_lead_table.c.lead_id == lead_table.c.id)
            )
            .where(campaign_company_table.c.assigned_sdr.in_(sdr_ids))
            .group_by(campaign_company_table.c.assigned_sdr)
        ).fetchall()
        campaigns_touched_map = {row.assigned_sdr: row.campaigns_touched for row in campaigns_touched_rows}

        activity_rows = conn.execute(
            select(
                campaign_company_table.c.assigned_sdr,
                lead_activity_table.c.type,
                func.count().label('count')
            )
            .select_from(
                campaign_company_table
                .join(mapping_table, campaign_company_table.c.id == mapping_table.c.campaign_company_id)
                .join(lead_table, lead_table.c.campaign_company_campaign_map_id == mapping_table.c.id)
                .join(campaign_lead_table, campaign_lead_table.c.lead_id == lead_table.c.id)
                .join(lead_activity_table, lead_activity_table.c.campaign_lead_id == campaign_lead_table.c.id)
            )
            .where(campaign_company_table.c.assigned_sdr.in_(sdr_ids))
            .group_by(campaign_company_table.c.assigned_sdr, lead_activity_table.c.type)
        ).fetchall()
        activity_map = {sdr_id: {'positive_replies': 0, 'meetings_booked': 0, 'deals_closed': 0} for sdr_id in sdr_ids}
        for row in activity_rows:
            sdr_id = row.assigned_sdr
            if row.type == 'replied':
                continue
            if row.type == 'meeting_booked':
                activity_map[sdr_id]['meetings_booked'] += row.count
            if row.type == 'deal_won' or row.type == 'deal_lost':
                activity_map[sdr_id]['deals_closed'] += row.count
        positive_reply_rows = conn.execute(
            select(
                campaign_company_table.c.assigned_sdr,
                func.count().label('count')
            )
            .select_from(
                campaign_company_table
                .join(mapping_table, campaign_company_table.c.id == mapping_table.c.campaign_company_id)
                .join(lead_table, lead_table.c.campaign_company_campaign_map_id == mapping_table.c.id)
                .join(campaign_lead_table, campaign_lead_table.c.lead_id == lead_table.c.id)
                .join(lead_activity_table, lead_activity_table.c.campaign_lead_id == campaign_lead_table.c.id)
            )
            .where(
                campaign_company_table.c.assigned_sdr.in_(sdr_ids),
                lead_activity_table.c.type == 'replied',
                lead_activity_table.c.description.ilike('%positive%')
            )
            .group_by(campaign_company_table.c.assigned_sdr)
        ).fetchall()
        for row in positive_reply_rows:
            activity_map[row.assigned_sdr]['positive_replies'] = row.count

        results = []
        for sdr in sdrs:
            sdr_id = sdr.id
            results.append(SDRDashboardStats(
                sdr_name=sdr.name,
                leads_emailed=leads_emailed_map.get(sdr_id, 0),
                positive_replies=activity_map[sdr_id]['positive_replies'],
                meetings_booked=activity_map[sdr_id]['meetings_booked'],
                deals_closed=activity_map[sdr_id]['deals_closed'],
                campaigns_touched=campaigns_touched_map.get(sdr_id, 0)
            ))
        total = len(results)
        return {
            "items": results[offset:offset+limit],
            "total": total
        }

@router.get("/{sdr_id}", response_model=SDRSchema)
def get_sdr(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
        return SDRSchema(**{k: sdr._mapping[k] for k in sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch SDR")

@router.put("/{sdr_id}", response_model=SDRSchema)
def update_sdr(
    sdr_id: str,
    sdr_data: SDRUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            
            if sdr_data.email and sdr_data.email != sdr._mapping['email']:
                result = conn.execute(
                    sdr_table.select().where(sdr_table.c.email == sdr_data.email)
                )
                existing_sdr = result.fetchone()
                if existing_sdr:
                    raise HTTPException(status_code=400, detail="SDR with this email already exists")
            
            update_data = {k: v for k, v in sdr_data.dict(exclude_unset=True).items() if v != sdr._mapping[k]}
            update_stmt = sdr_table.update().where(sdr_table.c.id == sdr_id).values(**update_data)
            result = conn.execute(update_stmt)
            conn.commit()
            updated_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.id == sdr_id)
            ).fetchone()
        return SDRSchema(**{k: updated_sdr._mapping[k] for k in updated_sdr._mapping.keys() if k in SDRSchema.__fields__})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update SDR")

@router.delete("/{sdr_id}")
def delete_sdr(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        ai_coaching_replies_table = get_table('ai_coaching_replies', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            conn.execute(ai_coaching_replies_table.delete().where(ai_coaching_replies_table.c.sdr_id == sdr_id))
            campaign_company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
            update_stmt = campaign_company_table.update().where(campaign_company_table.c.assigned_sdr == sdr_id).values(assigned_sdr=None)
            result = conn.execute(update_stmt)
            conn.commit()
            delete_stmt = sdr_table.delete().where(sdr_table.c.id == sdr_id)
            result = conn.execute(delete_stmt)
            conn.commit()
        return {"message": "SDR deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete SDR")

@router.post("/{sdr_id}/toggle-status")
def toggle_sdr_status(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        with db.bind.connect() as conn:
            result = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id))
            sdr = result.fetchone()
            if not sdr:
                raise HTTPException(status_code=404, detail="SDR not found")
            current_status = sdr._mapping['status']
            new_status = 'paused' if current_status == 'active' else 'active'
            sdr_data = {
                'status': new_status
            }
            update_stmt = sdr_table.update().where(sdr_table.c.id == sdr_id).values(**sdr_data)
            result = conn.execute(update_stmt)
            conn.commit()
            updated_sdr = conn.execute(
                sdr_table.select().where(sdr_table.c.id == sdr_id)
            ).fetchone()
        return {
            "message": f"SDR {new_status} successfully",
            "status": updated_sdr._mapping['status']
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to toggle SDR status") 