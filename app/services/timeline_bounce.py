from datetime import datetime, timedelta
from sqlalchemy import Table, MetaData, select, update, and_
import logging
from app.services.instantly import get_instantly_api_key, list_leads_in_campaign, delete_lead_by_id
from app.utils.db_utils import get_table

logger = logging.getLogger(__name__)

async def timeline_bounce_job(schema_name, bind, current_user):
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    lead_process_table = get_table('lead_process', schema_name, bind)
    leads_table = get_table('leads', schema_name, bind)
    campaign_company_campaign_map_table = get_table('campaign_company_campaign_map', schema_name, bind)
    companies_process_table = get_table('companies_process', schema_name, bind)

    with bind.begin() as conn:
        leads = conn.execute(
            select(lead_process_table)
            .where(
                (lead_process_table.c.status == 'email sent') &
                (lead_process_table.c.last_email_sent_at < one_week_ago)
            )
        ).fetchall()
        leads = [dict(row._mapping) for row in leads]

        for lead_process in leads:
            lead_id = lead_process['lead_id']
            lead_row = conn.execute(
                select(leads_table).where(leads_table.c.id == lead_id)
            ).fetchone()
            if not lead_row:
                continue
            lead = dict(lead_row._mapping)
            lead_email = lead['email']
            campaign_company_id = lead['campaign_company_id']
            company_campaign_maps = conn.execute(
                select(campaign_company_campaign_map_table)
                .where(campaign_company_campaign_map_table.c.campaign_company_id == campaign_company_id)
            ).fetchall()
            for company_campaign_map_row in company_campaign_maps:
                company_campaign_map = dict(company_campaign_map_row._mapping)
                campaign_id = company_campaign_map['campaign_id']
                company_process_row = conn.execute(
                    select(companies_process_table)
                    .where(companies_process_table.c.campaign_company_campaign_map_id == company_campaign_map['id'])
                ).fetchone()
                if company_process_row:
                    conn.execute(
                        update(companies_process_table)
                        .where(companies_process_table.c.id == company_process_row._mapping['id'])
                        .values(status='Bounced', updated_at=datetime.utcnow())
                    )
            conn.execute(
                update(lead_process_table)
                .where(lead_process_table.c.lead_id == lead_id)
                .values(status='bounced', last_updated_at=datetime.utcnow())
            )
            api_key = await get_instantly_api_key(bind, current_user)
            if api_key:
                try:
                    leads_in_campaign = await list_leads_in_campaign(api_key, campaign_id)
                    instantly_lead = next((l for l in leads_in_campaign if l.get("email") == lead_email), None)
                    if instantly_lead:
                        instantly_lead_id = instantly_lead.get("_id") or instantly_lead.get("id")
                        if instantly_lead_id:
                            await delete_lead_by_id(api_key, instantly_lead_id)
                except Exception as e:
                    logger.error(f"Failed to remove lead from Instantly campaign: {e}")

async def run_timeline_bounce_batch(run_multi_tenant_batch):
    try:
        await run_multi_tenant_batch(timeline_bounce_job)
    except Exception as e:
        logger.error(f"Error in timeline bounce batch: {str(e)}")
