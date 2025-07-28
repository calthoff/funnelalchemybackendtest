from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, select, update, insert
from app.db import get_db
from app.models.users import User
from datetime import datetime
import logging
import openai
from typing import Optional, Any, Dict
import re
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/webhook", tags=["webhook"])

class InstantlyReplyBody(BaseModel):
    text: str
    html: str = None

class InstantlyWebhookPayload(BaseModel):
    timestamp: str
    event_type: str
    workspace: str
    campaign_id: str
    campaign_name: str
    lead_email: Optional[str] = None
    email_account: Optional[str] = None
    unibox_url: Optional[str] = None
    step: Optional[int] = None
    variant: Optional[int] = None
    is_first: Optional[bool] = None
    email_id: Optional[str] = None
    email_subject: Optional[str] = None
    email_text: Optional[str] = None
    email_html: Optional[str] = None
    reply_text_snippet: Optional[str] = None
    reply_subject: Optional[str] = None
    reply_text: Optional[str] = None
    reply_html: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    jobTitle: Optional[str] = None
    linkedIn: Optional[str] = None
    location: Optional[str] = None
    firstName: Optional[str] = None
    companyName: Optional[str] = None
    personalization: Optional[str] = None
    extra: Dict[str, Any] = {}

    class Config:
        extra = "allow"

def get_user_by_campaign_id(db: Session, campaign_id: str) -> Optional[User]:
    try:
        with db.bind.connect() as conn:
            result = conn.execute(
                text("SELECT schema_name FROM public.user_directory")
            ).fetchall()
            
            for schema_row in result:
                schema_name = schema_row[0]
                try:
                    campaign_result = conn.execute(
                        text(f'SELECT id FROM "{schema_name}".campaigns WHERE id = :campaign_id'),
                        {"campaign_id": campaign_id}
                    ).fetchone()
                    
                    if campaign_result:
                        user_result = conn.execute(
                            text(f'SELECT * FROM "{schema_name}".users LIMIT 1')
                        ).fetchone()
                        
                        if user_result:
                            user_data = {k: user_result._mapping[k] for k in user_result._mapping.keys()}
                            user = User(**user_data)
                            user.schema_name = schema_name
                            return user
                            
                except Exception as e:
                    logging.warning(f"Error checking schema {schema_name}: {e}")
                    continue
                    
    except Exception as e:
        logging.error(f"Error finding user by campaign_id: {e}")
    return None

@router.post("/instantly")
async def instantly_webhook(
    payload: Request,
    db: Session = Depends(get_db)
):
    try:
        payload_data = await payload.json()
        logging.info(f"Instantly webhook payload: {payload_data}")
        
        try:
            webhook_data = InstantlyWebhookPayload(**payload_data)
        except Exception as e:
            logging.error(f"Failed to parse webhook payload: {e}")
            return {"status": "error", "message": "Invalid payload format"}
        
        event_type = webhook_data.event_type
        campaign_id = webhook_data.campaign_id
        lead_email = webhook_data.lead_email or webhook_data.email
        
        if not lead_email:
            logging.warning("No lead email found in webhook payload")
            return {"status": "error", "message": "No lead email provided"}
        
        current_user = get_user_by_campaign_id(db, campaign_id)
        if not current_user:
            logging.warning(f"No user found for campaign_id: {campaign_id}")
            return {"status": "error", "message": "User not found for campaign"}
        
        logging.info(f"Processing {event_type} event for user {current_user.email}, campaign {campaign_id}, lead {lead_email}")
        
        lead_table = get_table('leads', current_user.schema_name, db.bind)
        lead_process_table = get_table('lead_processes', current_user.schema_name, db.bind)
        campaign_company_campaign_map_table = get_table('campaign_company_campaign_map', current_user.schema_name, db.bind)
        companies_process_table = get_table('companies_process', current_user.schema_name, db.bind)

        with db.bind.begin() as conn:
            if event_type == "reply_received":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "Reply processed, but lead not found"}
                lead_id = lead._mapping['id']
                reply_snippet = webhook_data.reply_text_snippet
                if reply_snippet:
                    new_reply = {
                        "content": reply_snippet,
                        "timestamp": webhook_data.timestamp
                    }
                    lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                    if lead_process:
                        existing_replies = lead_process._mapping['reply_text_array'] or []
                        existing_replies.append(new_reply)
                        conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                            reply_text_array=existing_replies,
                            status="Replied",
                            last_updated_at=datetime.utcnow()
                        ))
                    else:
                        conn.execute(insert(lead_process_table).values(
                            id=uuid.uuid4(),
                            lead_id=lead_id,
                            status="Replied",
                            reply_text_array=[new_reply],
                            last_updated_at=datetime.utcnow()
                        ))
                    if campaign_id:
                        lead_row = conn.execute(select(lead_table).where(lead_table.c.id == lead_id)).fetchone()
                        if not lead_row:
                            logging.warning(f"Lead not found for lead_id: {lead_id}")
                            return {"status": "success", "message": "Reply processed successfully"}
                        campaign_company_campaign_map_id = lead_row._mapping['campaign_company_campaign_map_id']
                        logging.info(f"Found campaign_company_campaign_map_id: {campaign_company_campaign_map_id} for lead_id: {lead_id}")
                        if not campaign_company_campaign_map_id:
                            logging.warning(f"No campaign_company_campaign_map_id found for lead_id: {lead_id}")
                            return {"status": "success", "message": "Reply processed successfully"}
                        company_process = conn.execute(select(companies_process_table).where(
                            companies_process_table.c.campaign_company_campaign_map_id == campaign_company_campaign_map_id
                        )).fetchone()
                        if company_process:
                            if company_process._mapping['status'] == "Contacted":
                                conn.execute(update(companies_process_table).where(
                                    companies_process_table.c.id == company_process._mapping['id']
                                ).values(status="Replied", updated_at=datetime.utcnow()))
                                logging.info(f"Updated CompaniesProcess status from 'Contacted' to 'Replied' for mapping {campaign_company_campaign_map_id}")
                            else:
                                logging.info(f"CompaniesProcess status is '{company_process._mapping['status']}', not 'Contacted'. No update needed.")
                        else:
                            logging.warning(f"No CompaniesProcess found for campaign_company_campaign_map_id: {campaign_company_campaign_map_id}")
                            
            elif event_type == "email_sent":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "Email sent event processed, but lead not found"}
                lead_id = lead._mapping['id']
                lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                if lead_process:
                    conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                        status="email sent",
                        reply_classification="",
                        last_updated_at=datetime.utcnow()
                    ))
                else:
                    conn.execute(insert(lead_process_table).values(
                        id=uuid.uuid4(),
                        lead_id=lead_id,
                        status="email sent",
                        reply_classification="",
                        last_updated_at=datetime.utcnow()
                    ))
                    
            elif event_type == "email_bounced":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "Email bounced event processed, but lead not found"}
                lead_id = lead._mapping['id']
                campaign_company_campaign_map_id = lead._mapping['campaign_company_campaign_map_id']
                if campaign_company_campaign_map_id:
                    company_process = conn.execute(select(companies_process_table).where(
                        companies_process_table.c.campaign_company_campaign_map_id == campaign_company_campaign_map_id
                    )).fetchone()
                    if company_process:
                        conn.execute(update(companies_process_table).where(
                            companies_process_table.c.id == company_process._mapping['id']
                        ).values(status="Bounced", updated_at=datetime.utcnow()))
                else:
                    logging.warning(f"No campaign_company_campaign_map_id found for lead_id: {lead_id}")
                lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                if not lead_process:
                    conn.execute(insert(lead_process_table).values(
                        id=uuid.uuid4(),
                        lead_id=lead_id,
                        status="bounced",
                        reply_classification="",
                        last_updated_at=datetime.utcnow()
                    ))
                else:
                    conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                        status="bounced",
                        reply_classification="",
                        last_updated_at=datetime.utcnow()
                    ))
            
            elif event_type == "lead_interested":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "interested."}
                lead_id = lead._mapping['id']
                lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                if lead_process:
                    conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                        reply_classification="interested",
                        last_updated_at=datetime.utcnow()
                    ))
            
            elif event_type == "lead_not_interested":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "not_interested."}
                lead_id = lead._mapping['id']
                lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                if lead_process:
                    conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                        reply_classification="not_interested",
                        last_updated_at=datetime.utcnow()
                    ))

            elif event_type == "lead_neutral":
                lead = conn.execute(select(lead_table).where(lead_table.c.email == lead_email)).fetchone()
                if not lead:
                    logging.warning(f"Lead not found for email: {lead_email}")
                    return {"status": "success", "message": "neutral."}
                lead_id = lead._mapping['id']
                lead_process = conn.execute(select(lead_process_table).where(lead_process_table.c.lead_id == lead_id)).fetchone()
                if lead_process:
                    conn.execute(update(lead_process_table).where(lead_process_table.c.lead_id == lead_id).values(
                        reply_classification="neutral",
                        last_updated_at=datetime.utcnow()
                    ))

        logging.info(f"Successfully processed event {event_type}")
        return {"status": "success", "message": f"Event {event_type} processed successfully"}
        
    except Exception as e:
        logging.error(f"Failed to process webhook: {e}")
        return {"status": "error", "message": f"Failed to process webhook: {str(e)}"} 