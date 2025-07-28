from app.db import SessionLocal
from sqlalchemy import text
from app.utils.db_utils import get_table

async def run_multi_tenant_batch(process_midnight_batch):
    db = SessionLocal()
    try:
        schema_names = [row[0] for row in db.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'public', 'pg_toast', 'pg_stat_statements') AND schema_name NOT LIKE 'pg_%'")
        )]
        from app.db import engine
        for schema_name in schema_names:
            try:
                table_exists = db.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = :schema AND table_name = 'campaigns')"
                ), {"schema": schema_name}).scalar()
                if not table_exists:
                    continue
                campaign_table = get_table('campaigns', schema_name, engine)
                with engine.connect() as conn:
                    result = conn.execute(campaign_table.select())
                    campaigns = result.fetchall()
                for campaign in campaigns:
                    try:
                        await process_midnight_batch(db, str(campaign.id), schema_name)
                    except Exception as e:
                        db.rollback()
                        continue
            except Exception as e:
                db.rollback()
                continue
    except Exception as e:
        db.rollback()
    finally:
        db.close() 