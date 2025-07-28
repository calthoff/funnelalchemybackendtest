import csv
import os
import io
import uuid
from datetime import datetime, timezone
import openai
from typing import List, Dict, Any, Union
from collections import Counter
from sqlalchemy import MetaData, Table, select, and_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.services.instantly import check_leads_exist_in_instantly_batch, get_instantly_api_key
import logging
from app.utils.db_utils import get_table

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_lead_data_dict(lead_data: Union[Dict, Any]) -> Dict[str, Any]:
    if isinstance(lead_data, dict):
        return lead_data
    elif hasattr(lead_data, 'dict'):
        return lead_data.dict(exclude_unset=True)
    elif hasattr(lead_data, '__table__'):
        return {c.name: getattr(lead_data, c.name) for c in lead_data.__table__.columns}
    else:
        try:
            return vars(lead_data)
        except:
            return lead_data.__dict__ if hasattr(lead_data, '__dict__') else {}

def get_lead_attribute(lead_data: Union[Dict, Any], attr: str, default=None):
    if isinstance(lead_data, dict):
        return lead_data.get(attr, default)
    else:
        return getattr(lead_data, attr, default)

async def check_duplicates_before_upload(schema_name: str, bind, leads: List[Dict[str, Any]], campaign_id: str):
    leads_temp_table = get_table('leads_temp', schema_name, bind)
    duplicate_leads = []
    lead_emails = [get_lead_attribute(lead, 'email') for lead in leads if get_lead_attribute(lead, 'email')]
    if not lead_emails:
        return []
    with bind.connect() as conn:
        stmt = select(leads_temp_table).where(
            (leads_temp_table.c.campaign_id == str(campaign_id)) &
            (leads_temp_table.c.email.in_(lead_emails))
        )
        existing_leads = conn.execute(stmt).fetchall()
        existing_leads_map = {lead.email: lead for lead in existing_leads}
        for lead_data in leads:
            email = get_lead_attribute(lead_data, 'email')
            if email in existing_leads_map:
                existing_lead = existing_leads_map[email]
                duplicate_leads.append({
                    "existing_lead": {
                        "id": str(existing_lead.id),
                        "email": existing_lead.email,
                        "first_name": existing_lead.first_name,
                        "last_name": existing_lead.last_name,
                        "company_name": existing_lead.company_name,
                    },
                    "new_lead": get_lead_data_dict(lead_data)
                })
    return duplicate_leads

async def generate_icp_name(industry: str, company_size: str, location: str) -> str:
    return f"{company_size} {industry} Companies in {location}"

async def process_midnight_batch(db, campaign_id, schema_name):
    campaign_upload_mode_table = get_table('campaign_upload_mode', schema_name, db.bind)
    sdrs_table = get_table('sdrs', schema_name, db.bind)

    try:
        from sqlalchemy import text
        table_exists = db.execute(text(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = :schema AND table_name = 'campaigns'
            )"""), {"schema": schema_name}).scalar()
        if not table_exists:
            return {"status": "error", "message": f"campaigns table does not exist in schema {schema_name}"}
        campaigns_table = get_table('campaigns', schema_name, db.bind)
        with db.bind.connect() as conn:
            upload_mode = conn.execute(
                select(campaign_upload_mode_table).where(campaign_upload_mode_table.c.campaign_id == campaign_id)
            ).fetchone()
        if not upload_mode or not upload_mode.daily_push_limit:
            return {"status": "error", "message": "No daily push limit configured for this campaign"}
        daily_push_limit = upload_mode.daily_push_limit
        sdr_assignment_mode = upload_mode.sdr_assignment_mode or "round_robin"
        leads_temp_table = get_table('leads_temp', schema_name, db.bind)
        with db.bind.connect() as conn:
            not_pushed_temp_leads = conn.execute(
                select(leads_temp_table)
                .where((leads_temp_table.c.campaign_id == campaign_id) & (leads_temp_table.c.pushed_status == 'Not Pushed'))
                .order_by(leads_temp_table.c.created_at)
            ).fetchall()
        
        if not not_pushed_temp_leads:
            return {"status": "info", "message": "No leads to push"}
        
        to_push = min(daily_push_limit, len(not_pushed_temp_leads))
         
        if to_push == 0:
            return {"status": "info", "message": "No leads to push"}

        leads_to_process = [dict(row._mapping) for row in not_pushed_temp_leads[:to_push]]
        
        with db.bind.connect() as conn:
            campaign_row = conn.execute(
                select(campaigns_table).where(campaigns_table.c.id == campaign_id)
            ).fetchone()
        if not campaign_row:
            return {"status": "error", "message": "Campaign not found"}
            
        with db.bind.connect() as conn:
            sdr_rows = conn.execute(select(sdrs_table.c.id)).fetchall()
            sdrs = [str(row._mapping['id']) for row in sdr_rows]
        result = await process_leads_from_temp(
            schema_name=schema_name,
            bind=db.bind,
            campaign_id=campaign_id,
            temp_leads=leads_to_process,
            sdr_assignment_mode=sdr_assignment_mode,
            sdrs=sdrs,
            daily_push_limit=daily_push_limit
        )
        
        for temp_lead in leads_to_process:
            temp_lead['pushed_status'] = 'Pushed'
            temp_lead['updated_at'] = datetime.utcnow()
        
        db.commit()
        
        return {"status": "success", "message": f"Auto-pushed {len(leads_to_process)} leads", "result": result}
        
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error processing batch: {str(e)}"}

async def upload_leads_to_temp_with_scoring(
    schema_name, bind, campaign_id, new_leads, existing_leads, daily_push_limit, sdr_assignment_mode, sdrs, update_existing, api_key=None
):  
    leads_temp_table = get_table('leads_temp', schema_name, bind)
    leads_table = get_table('leads', schema_name, bind)

    with bind.begin() as conn:
        leads_added = 0
        for idx, lead_data in enumerate(new_leads):
            email = (lead_data.get('email') or '').strip().lower()
            existing_temp_lead = conn.execute(
                select(leads_temp_table).where(
                    (leads_temp_table.c.email == email) &
                    (leads_temp_table.c.campaign_id == campaign_id)
                )
            ).fetchone()
            valid_keys = set(c.name for c in leads_temp_table.columns)
            filtered_data = {k: v for k, v in lead_data.items() if k in valid_keys}
            lead_temp_data = {
                **filtered_data,
                'campaign_id': campaign_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'pushed_status': 'pushed' if idx < daily_push_limit else 'Not Pushed',
            }
            if 'id' not in lead_temp_data or not lead_temp_data['id']:
                lead_temp_data['id'] = uuid.uuid4()
            if existing_temp_lead:
                conn.execute(
                    leads_temp_table.update()
                    .where(
                        (leads_temp_table.c.email == email) &
                        (leads_temp_table.c.campaign_id == campaign_id)
                    )
                    .values(created_at=datetime.utcnow(), updated_at=datetime.utcnow())
                )
            else:
                conn.execute(leads_temp_table.insert().values(**lead_temp_data))
                leads_added += 1

        leads_updated = 0
        if update_existing:
            for lead_data in existing_leads:
                email = (lead_data.get('email') or '').strip().lower()
                valid_keys = set(c.name for c in leads_temp_table.columns)
                filtered_data = {k: v for k, v in lead_data.items() if k in valid_keys}
                conn.execute(
                    leads_temp_table.update()
                    .where(
                        (leads_temp_table.c.email == email) &
                        (leads_temp_table.c.campaign_id == campaign_id)
                    )
                    .values(**filtered_data, updated_at=datetime.utcnow())
                )
                valid_keys_leads = set(c.name for c in leads_table.columns)
                filtered_data_leads = {k: v for k, v in lead_data.items() if k in valid_keys_leads}
                conn.execute(
                    leads_table.update()
                    .where(leads_table.c.email == email)
                    .values(**filtered_data_leads, updated_at=datetime.utcnow())
                )
                leads_updated += 1

        sorted_leads_temp = conn.execute(
            select(leads_temp_table)
            .where((leads_temp_table.c.campaign_id == campaign_id) & (leads_temp_table.c.pushed_status == 'pushed'))
            .order_by(leads_temp_table.c.created_at.desc())
            .limit(daily_push_limit)
        ).fetchall()
        leads_to_process = [dict(row._mapping) for row in sorted_leads_temp]

    process_result = await process_leads_from_temp(
        schema_name=schema_name,
        bind=bind,
        campaign_id=campaign_id,
        temp_leads=leads_to_process,
        sdr_assignment_mode=sdr_assignment_mode,
        sdrs=sdrs,
        daily_push_limit=daily_push_limit,
        api_key=api_key
    )

    return {
        "leads_added": leads_added,
        "leads_updated": leads_updated,
        "leads_processed": len(leads_to_process),
        "process_result": process_result,
    }

async def process_leads_from_temp(
    schema_name, bind, campaign_id, temp_leads, sdr_assignment_mode, sdrs, daily_push_limit, api_key=None
):
    companies_table = get_table('campaign_companies', schema_name, bind)
    leads_table = get_table('leads', schema_name, bind)
    campaign_leads_table = get_table('campaign_leads', schema_name, bind)
    campaign_company_campaign_map_table = get_table('campaign_company_campaign_map', schema_name, bind)
    companies_process_table = get_table('companies_process', schema_name, bind)
    icps_table = get_table('icps', schema_name, bind)
    campaign_icps_table = get_table('campaign_icps', schema_name, bind)

    with bind.connect() as conn:
        website_groups = {}
        for lead in temp_leads:
            website = (lead.get('website') or '').strip().lower()
            website_groups.setdefault(website, []).append(lead)

        created_leads = []
        created_companies = []
        created_mappings = []
        created_icps = []
        sdr_index = 0

        for website, group in website_groups.items():
            company = None
            if website:
                company = conn.execute(
                    select(companies_table).where(companies_table.c.website == website)
                ).fetchone()
            if not company:
                if len(group) == 1:
                    company_info = group[0]
                elif len(group) == 2:
                    company_info = group[0]
                else:
                    company_info = {}
                    for field in ['name', 'company_name', 'industry', 'location', 'tags', 'description', 'revenue_range', 'company_size', 'linkedin_url', 'funding_round', 'tech_stack']:
                        values = [lead.get(field) for lead in group if lead.get(field)]
                        if values:
                            company_info[field] = Counter(values).most_common(1)[0][0]
                        else:
                            company_info[field] = ""
                if len(group) == 1:
                    company_name = company_info.get('company_name') or company_info.get('name') or "Unknown Company"
                elif len(group) == 2:
                    company_name = company_info.get('company_name') or company_info.get('name') or "Unknown Company"
                else:
                    name_values = [lead.get('company_name') or lead.get('name') for lead in group if lead.get('company_name') or lead.get('name')]
                    company_name = Counter(name_values).most_common(1)[0][0] if name_values else "Unknown Company"
                company_id = uuid.uuid4()
                valid_keys = set(c.name for c in companies_table.columns)
                filtered_data = {k: v for k, v in {
                    'id': company_id,
                    'name': company_name,
                    'website': website,
                    'industry': company_info.get('industry', ''),
                    'location': company_info.get('location', ''),
                    'tags': company_info.get('tags', ''),
                    'description': company_info.get('description', ''),
                    'revenue_range': company_info.get('revenue_range', ''),
                    'company_size': company_info.get('company_size', ''),
                    'linkedin_url': company_info.get('linkedin_url', ''),
                    'funding_round': company_info.get('funding_round', ''),
                    'tech_stack': company_info.get('tech_stack', ''),
                    'assigned_sdr': sdrs[sdr_index % len(sdrs)] if sdrs and sdr_assignment_mode != 'manual' else None,
                }.items() if k in valid_keys}
                conn.execute(companies_table.insert().values(**filtered_data))
                created_companies.append(str(company_id))
            else:
                company_id = company.id

            company_score = None
            mapping = conn.execute(
                select(campaign_company_campaign_map_table).where(
                    (campaign_company_campaign_map_table.c.campaign_id == campaign_id) &
                    (campaign_company_campaign_map_table.c.campaign_company_id == company_id)
                )
            ).fetchone()
            if not mapping:
                mapping_id = uuid.uuid4()
                conn.execute(campaign_company_campaign_map_table.insert().values(
                    id=mapping_id,
                    campaign_company_id=company_id,
                    campaign_id=campaign_id,
                    company_score=company_score,
                    context='',
                    created_at=datetime.utcnow()
                ))
                created_mappings.append(str(mapping_id))
            else:
                mapping_id = mapping.id

            for lead in group:
                email = (lead.get('email') or '').strip().lower()
                prompt = f"Score this lead based on their job title, company, and industry: {lead}"
                try:
                    response = openai.Completion.create(
                        engine="text-davinci-003",
                        prompt=prompt,
                        max_tokens=1,
                        temperature=0
                    )
                    lead_score = int(response.choices[0].text.strip())
                except Exception:
                    lead_score = None

                icp_criteria = {
                    "industry": lead.get('industry', ''),
                    "location": lead.get('location', '')
                }
                icp = conn.execute(
                    select(icps_table).where(
                        (icps_table.c.criteria['industry'].astext == icp_criteria['industry']) &
                        (icps_table.c.criteria['location'].astext == icp_criteria['location'])
                    )
                ).fetchone()
                if not icp:
                    company_size = icp_criteria.get('company_size')
                    industry = icp_criteria.get('industry')
                    location = icp_criteria.get('location')
                    parts = []
                    if company_size: parts.append(company_size)
                    if industry: parts.append(industry)
                    if location:
                        parts.append(f"Companies in {location}")
                    else:
                        parts.append("Companies")
                    icp_name = " ".join(parts)
                    icp_id = uuid.uuid4()
                    conn.execute(icps_table.insert().values(
                        id=icp_id,
                        name=icp_name,
                        description="",
                        criteria=icp_criteria,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
                    created_icps.append(str(icp_id))
                else:
                    icp_id = icp.id

                campaign_icp_mapping = conn.execute(
                    select(campaign_icps_table).where(
                        (campaign_icps_table.c.campaign_id == campaign_id) &
                        (campaign_icps_table.c.icp_id == icp_id)
                    )
                ).fetchone()
                if not campaign_icp_mapping:
                    conn.execute(campaign_icps_table.insert().values(
                        id=uuid.uuid4(),
                        campaign_id=campaign_id,
                        icp_id=icp_id,
                    ))

                for idx, lead in enumerate(group):
                    email = (lead.get('email') or '').strip().lower()
                    name = (lead.get('first_name', '') + ' ' + lead.get('last_name', '')).strip()
                    if not email:
                        continue
                    existing_lead = conn.execute(
                        select(leads_table).where(
                            (leads_table.c.email == email) &
                            (leads_table.c.campaign_company_campaign_map_id == mapping_id)
                        )
                    ).fetchone()
                    if existing_lead:
                        continue
                    lead_id = uuid.uuid4()
                    valid_keys = set(c.name for c in leads_table.columns)
                    filtered_data = {k: v for k, v in {
                        'id': lead_id,
                        'campaign_company_campaign_map_id': mapping_id,
                        'icp_id': icp_id,
                        'first_name': lead.get('first_name'),
                        'last_name': lead.get('last_name'),
                        'email': email,
                        'company_name': lead.get('company_name'),
                        'job_title': lead.get('job_title'),
                        'website': lead.get('website'),
                        'description': lead.get('description'),
                        'industry': lead.get('industry'),
                        'revenue_range': lead.get('revenue_range'),
                        'company_size': lead.get('company_size'),
                        'linkedin_url': lead.get('linkedin_url'),
                        'phone_number': lead.get('phone_number'),
                        'tags': lead.get('tags'),
                        'tech_stack': lead.get('tech_stack'),
                        'funding_round': lead.get('funding_round'),
                        'location': lead.get('location'),
                        'department': lead.get('department'),
                        'seniority': lead.get('seniority'),
                        'personal_label': lead.get('personal_label'),
                        'source_notes': lead.get('source_notes'),
                        'lead_score': lead_score,
                        'personalization': lead.get('personalization'),
                        'clay_enrichment': lead.get('clay_enrichment'),
                        'enrichment_source': lead.get('enrichment_source'),
                        'enriched_at': lead.get('enriched_at'),
                        'pushed_status': lead.get('pushed_status'),
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }.items() if k in valid_keys}
                    conn.execute(leads_table.insert().values(**filtered_data))
                    created_leads.append(str(lead_id))

                    campaign_lead_id = uuid.uuid4()
                    conn.execute(campaign_leads_table.insert().values(
                        id=campaign_lead_id,
                        campaign_id=campaign_id,
                        lead_id=lead_id,
                    ))

                    lead_activity_table = get_table('lead_activities', schema_name, bind)
                    conn.execute(lead_activity_table.insert().values(
                        id=uuid.uuid4(),
                        campaign_lead_id=campaign_lead_id,
                        type='created',
                        source=name,
                        description=f"Lead uploaded: {email}",
                        timestamp=datetime.utcnow()
                    ))

                try:
                    company_score_prompt = f"Score this company for the campaign: {filtered_data}"
                    response = openai.Completion.create(
                        engine="text-davinci-003",
                        prompt=company_score_prompt,
                        max_tokens=1,
                        temperature=0
                    )
                    company_score = int(response.choices[0].text.strip())
                except Exception:
                    company_score = None

                mapping = conn.execute(
                    select(campaign_company_campaign_map_table).where(
                        (campaign_company_campaign_map_table.c.campaign_id == campaign_id) &
                        (campaign_company_campaign_map_table.c.campaign_company_id == company_id)
                    )
                ).fetchone()
                if not mapping:
                    mapping_id = uuid.uuid4()
                    conn.execute(campaign_company_campaign_map_table.insert().values(
                        id=mapping_id,
                        campaign_company_id=company_id,
                        campaign_id=campaign_id,
                        company_score=company_score,
                        context='',
                        created_at=datetime.utcnow()
                    ))
                    conn.execute(companies_process_table.insert().values(
                        id=uuid.uuid4(),
                        campaign_company_campaign_map_id=mapping_id,
                        status='Contacted',
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    ))
                else:
                    mapping_id = mapping.id
                    conn.execute(campaign_company_campaign_map_table.update().where(
                        campaign_company_campaign_map_table.c.id == mapping_id
                    ).values(
                        company_score=company_score
                    ))
                    process = conn.execute(
                        select(companies_process_table).where(
                            companies_process_table.c.campaign_company_campaign_map_id == mapping_id
                        )
                    ).fetchone()
                    if process:
                        conn.execute(companies_process_table.update().where(
                            companies_process_table.c.id == process.id
                        ).values(
                            status='Contacted'
                        ))
                    else:
                        conn.execute(companies_process_table.insert().values(
                            id=uuid.uuid4(),
                            campaign_company_campaign_map_id=mapping_id,
                            status='Contacted',
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        ))
                campaign_upload_mode_table = get_table('campaign_upload_mode', schema_name, bind)
                upload_mode_data = {
                    'id': uuid.uuid4(), 
                    'campaign_id': campaign_id,
                    'sdr_assignment_mode': sdr_assignment_mode,
                    'daily_push_limit': daily_push_limit,
                }
                stmt = pg_insert(campaign_upload_mode_table).values(**upload_mode_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['campaign_id'],
                    set_={
                        'sdr_assignment_mode': sdr_assignment_mode,
                        'daily_push_limit': daily_push_limit,
                    }
                )
                conn.execute(stmt)
        conn.commit()
    return {
        "created_leads": created_leads,
        "created_companies": created_companies,
        "created_mappings": created_mappings,
        "created_icps": created_icps
    }

def normalize_website(website):
    return website.strip().lower() if website else "" 