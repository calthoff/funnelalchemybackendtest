from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case, distinct
from app.db import get_db
from app.schemas.icps import ICPRead, ICPDashboardStats, ICPDashboardStatsPage
from typing import List
from app.models.users import User
from app.utils.auth import get_current_user
from app.utils.db_utils import get_table

router = APIRouter(prefix="/icps", tags=["icps"])

@router.get("/", response_model=List[ICPRead])
def get_icps(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    icp_table = get_table('icps', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        result = conn.execute(icp_table.select())
        icps = result.fetchall()
    return [ICPRead(**{k: icp._mapping[k] for k in icp._mapping.keys() if k in ICPRead.__fields__}) for icp in icps]

@router.get("/dashboard", response_model=ICPDashboardStatsPage)
def get_icp_dashboard_stats(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    icp_table = get_table('icps', current_user.schema_name, db.bind)
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
    campaign_company_table = get_table('campaign_companies', current_user.schema_name, db.bind)
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
    campaign_company_campaign_map_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
    campaign_lead_table = get_table('campaign_leads', current_user.schema_name, db.bind)

    main_query = (
        select(
            icp_table.c.id.label('icp_id'),
            icp_table.c.name.label('icp_name'),
            func.count(distinct(lead_table.c.id)).label('leads_pushed'),
            func.coalesce(
                func.sum(
                    case(
                        ((lead_activity_table.c.type == 'replied') & (lead_activity_table.c.description.ilike('%positive%')), 1),
                        else_=0
                    )
                ),
                0
            ).label('positive_replies'),
            func.coalesce(
                func.sum(
                    case(
                        (lead_activity_table.c.type == 'meeting_booked', 1),
                        else_=0
                    )
                ),
                0
            ).label('meetings_booked'),
            func.coalesce(
                func.sum(
                    case(
                        ((lead_activity_table.c.type == 'deal_won') | (lead_activity_table.c.type == 'deal_lost'), 1),
                        else_=0
                    )
                ),
                0
            ).label('deals_closed'),
            func.array_agg(distinct(sdr_table.c.name)).label('sdrs_assigned')
        )
        .select_from(
            icp_table
            .outerjoin(lead_table, lead_table.c.icp_id == icp_table.c.id)
            .outerjoin(campaign_company_campaign_map_table, lead_table.c.campaign_company_campaign_map_id == campaign_company_campaign_map_table.c.id)
            .outerjoin(campaign_company_table, campaign_company_campaign_map_table.c.campaign_company_id == campaign_company_table.c.id)
            .outerjoin(sdr_table, campaign_company_table.c.assigned_sdr == sdr_table.c.id)
            .outerjoin(campaign_lead_table, campaign_lead_table.c.lead_id == lead_table.c.id)
            .outerjoin(lead_activity_table, lead_activity_table.c.campaign_lead_id == campaign_lead_table.c.id)
        )
        .group_by(icp_table.c.id, icp_table.c.name)
        .order_by(icp_table.c.name)
    )

    with db.bind.connect() as conn:
        all_rows = conn.execute(main_query).fetchall()
        total = len(all_rows)
        rows = all_rows[offset:offset+limit]
        results = []
        for row in rows:
            leads_pushed = row.leads_pushed or 0
            meetings_booked = row.meetings_booked or 0
            close_rate = (meetings_booked / leads_pushed) if leads_pushed else 0.0
            sdrs_assigned = [s for s in (row.sdrs_assigned or []) if s]
            deals_closed = row.deals_closed or 0
            results.append(ICPDashboardStats(
                icp_name=row.icp_name,
                leads_pushed=leads_pushed,
                positive_replies=row.positive_replies or 0,
                meetings_booked=meetings_booked,
                close_rate=close_rate,
                sdrs_assigned=sdrs_assigned,
                deals_closed=deals_closed
            ))
        return {
            "items": results,
            "total": total
        }