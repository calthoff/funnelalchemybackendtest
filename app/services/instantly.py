import httpx
import logging
from typing import Dict, Any, List
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_instantly_campaigns(api_key):
    url = "https://api.instantly.ai/api/v2/campaigns"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("items", [])

async def list_leads_in_campaign(api_key: str, campaign_id: str) -> List[Dict[str, Any]]:
    url = "https://api.instantly.ai/api/v2/leads/list"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"campaign": campaign_id}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("items", [])

async def delete_lead_by_id(api_key: str, lead_id: str):
    url = f"https://api.instantly.ai/api/v2/leads/{lead_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()

async def add_lead_to_instantly(api_key: str, lead_data: Dict[str, Any]):
    url = "https://api.instantly.ai/api/v2/leads"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=lead_data)
        response.raise_for_status()
        return response.json()

async def get_instantly_api_key(db, current_user):
    from sqlalchemy import Table, MetaData, select
    metadata = MetaData(schema=current_user.schema_name)
    api_info_table = Table('api_info', metadata, autoload_with=db.bind)
    
    with db.bind.connect() as conn:
        result = conn.execute(
            select(api_info_table).where(api_info_table.c.api_type == "instantly")
        ).fetchone()
        return result._mapping["api_key"] if result else None

async def remove_leads_from_instantly_on_company_delete(api_key, campaign_id, primary_lead):
    try:
        lead_data = primary_lead.get('primary_lead', primary_lead)
        
        if not lead_data or 'email' not in lead_data:
            return {"success": False, "error": "Primary lead data is missing or invalid"}
        
        campaign_leads = await list_leads_in_campaign(api_key, str(campaign_id))
        for campaign_lead in campaign_leads:
            if campaign_lead.get('email', '').lower() == lead_data['email'].lower():
                await delete_lead_by_id(api_key, campaign_lead['id'])
    except Exception as e:
        return {"success": False, "error": f"Failed to delete lead from Instantly: {str(e)}"}
    return {"success": True, "message": f"Successfully deleted primary lead {lead_data['email']} from Instantly campaign."}  

async def check_leads_exist_in_instantly(api_key, campaign_id, primary_lead):
    lead_data = primary_lead.get('primary_lead', primary_lead)
    if not lead_data or 'email' not in lead_data:
        return False, "Primary lead data is missing or invalid"
    try:
        campaign_leads = await list_leads_in_campaign(api_key, str(campaign_id))
    except Exception as e:
        return False, f"Failed to fetch leads from Instantly: {str(e)}"
    if not campaign_leads:
        return False, "No leads found in Instantly campaign (or API key is invalid)"
    for campaign_lead in campaign_leads:
        if campaign_lead.get('email', '').lower() == lead_data['email'].lower():
            return True, f"Primary lead {lead_data['email']} already exists in Instantly campaign"

    return False, "Primary lead does not exist in Instantly campaign"

async def check_leads_exist_in_instantly_batch(api_key, campaign_id, emails):
    try:
        campaign_leads = await list_leads_in_campaign(api_key, str(campaign_id))
    except Exception as e:
        return {}, f"Failed to fetch leads from Instantly: {str(e)}"
    if not campaign_leads:
        return {}, None
    existing_leads = {l.get('email', '').lower(): l for l in campaign_leads if l.get('email')}
    input_emails = set(e.lower() for e in emails if e)
    found_leads = {email: existing_leads[email] for email in input_emails if email in existing_leads}
    return found_leads, None

async def process_company_approval_for_instantly(api_key, campaign_id, primary_lead):
    if not api_key:
        return {"success": False, "error": "Instantly.ai API key not configured"}

    if not primary_lead:
        return {"success": False, "error": "No primary lead provided"}
    
    lead_data = primary_lead.get('primary_lead', primary_lead)
    
    lead_payload = {
        "campaign": str(campaign_id),
        "email": lead_data['email'],
        "first_name": lead_data['first_name'],
        "last_name": lead_data['last_name'],
        "company_name": lead_data.get('company_name') or ""
    }
    
    try:
        await add_lead_to_instantly(api_key, lead_payload)
    except Exception as e:
        error_details = str(e.response.text) if hasattr(e, 'response') else str(e)
        return {"success": False, "error": f"Failed to add lead to Instantly. Please check instantly api key."}

    return {"success": True, "message": f"Successfully added primary lead {lead_data['email']} to Instantly campaign."}