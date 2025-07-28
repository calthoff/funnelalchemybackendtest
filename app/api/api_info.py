from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text, Table, MetaData
from app.db import get_db
from app.models.api_info import APIInfo
from app.schemas.api_info import APIInfoCreate, APIInfoRead, APIInfoUpdate
from app.models.users import User
from app.utils.auth import get_current_user
from uuid import UUID
from app.services.instantly import fetch_instantly_campaigns
from app.models.campaigns import Campaign
import uuid
from app.utils.db_utils import get_table

router = APIRouter(prefix="/api-info", tags=["api_info"])

async def sync_instantly_campaigns(db: Session, api_key: str, current_user: User, is_update: bool = False):
    try:
        campaign_table = get_table('campaigns', current_user.schema_name, db.bind)
        campaigns = await fetch_instantly_campaigns(api_key)
        print(f"Fetched {len(campaigns)} campaigns from Instantly.")
        new_campaigns_count = 0
        updated_campaigns_count = 0
        with db.bind.connect() as conn:
            existing_campaigns = conn.execute(campaign_table.select()).fetchall()
            existing_campaign_ids = {str(campaign.id) for campaign in existing_campaigns}
            for campaign in campaigns:
                status = campaign.get("status")
                is_paused = True if status == 2 else False
                campaign_type = None
                sequences = campaign.get("sequences", [])
                if sequences and sequences[0].get("steps"):
                    steps = sequences[0]["steps"]
                    if steps and steps[0].get("type"):
                        campaign_type = steps[0]["type"]
                if not campaign_type:
                    campaign_type = "unknown"
                schedule = campaign.get("campaign_schedule", {})
                start_date = schedule.get("start_date") if schedule else None
                end_date = schedule.get("end_date") if schedule else None
                if start_date == "":
                    start_date = None
                if end_date == "":
                    end_date = None
                campaign_id = campaign.get("id", str(uuid.uuid4()))
                if isinstance(campaign_id, str):
                    try:
                        campaign_id = uuid.UUID(campaign_id)
                    except Exception:
                        campaign_id = uuid.uuid4()
                campaign_id_str = str(campaign_id)
                if campaign_id_str in existing_campaign_ids:
                    existing_campaign = conn.execute(
                        campaign_table.select().where(campaign_table.c.id == campaign_id)
                    ).fetchone()
                    if existing_campaign:
                        existing_campaign_dict = {k: existing_campaign._mapping[k] for k in existing_campaign._mapping.keys()}
                        existing_campaign_dict["name"] = campaign.get("name", "")
                        existing_campaign_dict["campaign_type"] = campaign_type
                        existing_campaign_dict["is_paused"] = is_paused
                        existing_campaign_dict["start_date"] = start_date
                        existing_campaign_dict["end_date"] = end_date
                        update_stmt = campaign_table.update().where(campaign_table.c.id == campaign_id).values(**existing_campaign_dict)
                        conn.execute(update_stmt)
                        updated_campaigns_count += 1
                        print(f"Updated existing campaign: {campaign.get('name')}")
                else:
                    new_campaign = {
                        "id": campaign_id,
                        "name": campaign.get("name", ""),
                        "campaign_type": campaign_type,
                        "is_paused": is_paused,
                        "start_date": start_date,
                        "end_date": end_date,
                        "campaign_manager_id": None
                    }
                    conn.execute(campaign_table.insert().values(**new_campaign))
                    new_campaigns_count += 1
                    print(f"Added new campaign: {campaign.get('name')}")
            conn.commit()
            print(f"Campaign sync completed: {new_campaigns_count} new, {updated_campaigns_count} updated")
        return True
    except Exception as e:
        print(f"Error syncing Instantly campaigns: {e}")
        return False

@router.post("/", response_model=APIInfoRead)
async def create_api_info(
    payload: APIInfoCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_info_table = get_table('api_info', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        insert_stmt = api_info_table.insert().values(id=uuid.uuid4(), **payload.dict())
        result = conn.execute(insert_stmt)
        conn.commit()
        new_api_info = conn.execute(
            api_info_table.select().where(api_info_table.c.api_type == payload.api_type)
        ).fetchone()
    if payload.api_type == "instantly":
        sync_success = await sync_instantly_campaigns(db, payload.api_key, current_user, is_update=False)
        if not sync_success:
            print(f"Warning: Campaign sync failed for API key, but API info was saved")
    return APIInfoRead(**{k: new_api_info._mapping[k] for k in new_api_info._mapping.keys() if k in APIInfoRead.__fields__})

@router.get("/keys/{api_type}", response_model=APIInfoRead)
def get_api_key(
    api_type: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_info_table = get_table('api_info', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        api_info = conn.execute(
            api_info_table.select().where(api_info_table.c.api_type == api_type)
        ).fetchone()
    if not api_info:
        raise HTTPException(status_code=404, detail="API key not found")
    return APIInfoRead(**{k: api_info._mapping[k] for k in api_info._mapping.keys() if k in APIInfoRead.__fields__})

@router.put("/{api_type}", response_model=APIInfoRead)
async def update_api_key(
    api_type: str,
    payload: APIInfoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print("UPDATE API KEY CALLED", api_type)
    api_info_table = get_table('api_info', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        api_info = conn.execute(
            api_info_table.select().where(api_info_table.c.api_type == api_type)
        ).fetchone()
        if not api_info:
            print("API key not found for update")
            raise HTTPException(status_code=404, detail="API key not found")
        update_data = {k: v for k, v in payload.dict(exclude_unset=True).items()}
        update_stmt = api_info_table.update().where(api_info_table.c.api_type == api_type).values(**update_data)
        conn.execute(update_stmt)
        conn.commit()
        updated_api_info = conn.execute(
            api_info_table.select().where(api_info_table.c.api_type == api_type)
        ).fetchone()
    if api_type == "instantly":
        api_key_to_use = payload.api_key if payload.api_key else api_info._mapping["api_key"]
        sync_success = await sync_instantly_campaigns(db, api_key_to_use, current_user, is_update=True)
        if not sync_success:
            print(f"Warning: Campaign sync failed for updated API key, but API info was updated")
    return APIInfoRead(**{k: updated_api_info._mapping[k] for k in updated_api_info._mapping.keys() if k in APIInfoRead.__fields__})

@router.delete("/{api_type}")
def delete_api_key(
    api_type: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    api_info_table = get_table('api_info', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        api_info = conn.execute(
            api_info_table.select().where(api_info_table.c.api_type == api_type)
        ).fetchone()
        if not api_info:
            raise HTTPException(status_code=404, detail="API key not found")
        delete_stmt = api_info_table.delete().where(api_info_table.c.api_type == api_type)
        conn.execute(delete_stmt)
        conn.commit()
    print(f"Deleted API key for {api_type}. Campaigns are preserved.")
    return {"ok": True} 