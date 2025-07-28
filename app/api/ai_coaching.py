from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.db import get_db
from app.models.ai_coaching_reply import AICoachingReply as AICoachingReplyModel
from app.schemas.ai_coaching_reply import AICoachingRepliesResponse, AICoachingReply
from app.models.sdrs import SDR
from app.utils.auth import get_current_user
from app.utils.db_utils import get_table
from app.models.users import User

router = APIRouter(prefix="/ai-coaching", tags=["ai_coaching"])

@router.get("/sdr/{sdr_id}/replies", response_model=AICoachingRepliesResponse)
def get_sdr_ai_coaching_replies(
    sdr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ai_coaching_table = get_table('ai_coaching_replies', current_user.schema_name, db.bind)
    sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
    with db.bind.connect() as conn:
        sdr_row = conn.execute(sdr_table.select().where(sdr_table.c.id == sdr_id)).fetchone()
        if not sdr_row:
            raise HTTPException(status_code=404, detail="SDR not found")
        sdr_name = sdr_row._mapping['name']
        replies = conn.execute(
            select(ai_coaching_table).where(ai_coaching_table.c.sdr_id == sdr_id).order_by(desc(ai_coaching_table.c.datetime_sent)).limit(15)
        ).fetchall()
        reply_objs = [AICoachingReply(**{k: r._mapping[k] for k in r._mapping.keys() if k in AICoachingReply.__fields__}) for r in replies]
        return AICoachingRepliesResponse(
            sdr_id=sdr_id,
            sdr_name=sdr_name,
            replies=reply_objs
        ) 