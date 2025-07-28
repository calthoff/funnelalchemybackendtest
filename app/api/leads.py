from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text, select, update
from app.db import get_db
from app.schemas.leads import LeadRead, LeadUpdate
from app.schemas.leads_temp import LeadTempRead
from typing import List
from app.models.users import User
from app.utils.auth import get_current_user
import uuid
from app.utils.db_utils import get_table
from datetime import datetime

router = APIRouter(prefix="/leads", tags=["leads"])

@router.get("/", response_model=List[LeadRead])
def get_all_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        result = conn.execute(lead_table.select())
        leads = result.fetchall()
    return [LeadRead(**{k: lead[k] for k in lead.keys() if k in LeadRead.__fields__}) for lead in leads]

@router.get("/temp", response_model=List[LeadTempRead])
def get_all_leads_temp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead_temp_table = get_table('leads_temp', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        result = conn.execute(lead_temp_table.select())
        leads_temp = result.fetchall()
    return [LeadTempRead(**{k: lead_temp[k] for k in lead_temp.keys() if k in LeadTempRead.__fields__}) for lead_temp in leads_temp]

@router.put("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: str,
    lead_update: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    lead_uuid = uuid.UUID(lead_id)
    update_data = lead_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(value, 'scheme') and hasattr(value, 'host'):
            update_data[key] = str(value)
    with db.bind.begin() as conn:
        lead_row = conn.execute(select(lead_table).where(lead_table.c.id == lead_uuid)).fetchone()
        if not lead_row:
            raise HTTPException(status_code=404, detail="Lead not found")
        conn.execute(update(lead_table).where(lead_table.c.id == lead_uuid).values(**update_data))
        updated_row = conn.execute(select(lead_table).where(lead_table.c.id == lead_uuid)).fetchone()
        if not updated_row:
            raise HTTPException(status_code=500, detail="Failed to update lead")
        lead_dict = {k: updated_row._mapping[k] for k in updated_row._mapping.keys() if k in LeadRead.__fields__}

        campaign_leads_table = get_table('campaign_leads', current_user.schema_name, db.bind)
        lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
        campaign_leads = conn.execute(select(campaign_leads_table).where(campaign_leads_table.c.lead_id == lead_uuid)).fetchall()
        for cl in campaign_leads:
            conn.execute(lead_activity_table.insert().values(
                id=uuid.uuid4(),
                campaign_lead_id=cl.id,
                type='updated',
                source='manual',
                description=f"Lead updated: {lead_dict.get('email', '')}",
                timestamp=text('CURRENT_TIMESTAMP')
            ))
    return LeadRead(**lead_dict)

@router.post("/add-activity", response_model=dict)
def add_lead_activity(
    lead_id: str = Body(...),
    campaign_id: str = Body(...),
    type: str = Body(...),
    description: str = Body(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print('--------')
    lead_table = get_table('leads', current_user.schema_name, db.bind)
    campaign_leads_table = get_table('campaign_leads', current_user.schema_name, db.bind)
    lead_activity_table = get_table('lead_activities', current_user.schema_name, db.bind)
    import uuid
    from datetime import datetime
    with db.bind.begin() as conn:
        cl_row = conn.execute(
            select(campaign_leads_table.c.id).where(
                (campaign_leads_table.c.lead_id == lead_id) & (campaign_leads_table.c.campaign_id == campaign_id)
            )
        ).fetchone()
        if not cl_row:
            raise HTTPException(status_code=404, detail="Campaign lead not found for this lead and campaign")
        campaign_lead_id = cl_row._mapping['id']
        conn.execute(
            lead_activity_table.insert().values(
                id=uuid.uuid4(),
                campaign_lead_id=campaign_lead_id,
                type=type,
                source=current_user.full_name if hasattr(current_user, 'full_name') else current_user.email,
                description=description,
                timestamp=datetime.utcnow()
            )
        )
    return {"status": "success"}
