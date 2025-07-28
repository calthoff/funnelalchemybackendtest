from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .db import Base, engine
from .api.auth import router as auth_router
from app.models.user_directory import UserDirectory
import sqlalchemy
from app.api.api_info import router as api_info_router
from app.api.campaign import router as campaign_router
from app.api.campaign_company import router as campaign_company_router
from app.api.leads import router as leads_router
from app.api.icps import router as icps_router
from app.api.sdrs import router as sdrs_router
from app.api.users import router as users_router
# from app.api.webhook import router as webhook_router
from app.api.ai_coaching import router as ai_coaching_router
import os
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.multi_tenant_batch import run_multi_tenant_batch
from app.services.campaign import process_midnight_batch
from app.services.timeline_bounce import timeline_bounce_job
from app.utils.db_utils import get_table
from app.db import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Funnel Alchemy API",
    description="API for managing sales pipeline and lead generation",
    version="1.0.0"
)

origins = [
    "https://funnelalchemy.onrender.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

@app.get("/")
def root():
    return {"message": "Funnel Alchemy API"}

def create_public_tables():
    inspector = sqlalchemy.inspect(engine)
    if not inspector.has_table('user_directory'):
        UserDirectory.__table__.create(engine, checkfirst=True)
        print("Created user_directory table in public schema")
    else:
        print("user_directory table already exists in public schema")

@app.on_event("startup")
async def startup_db_client():
    create_public_tables()

SCHEMAS = ["public"]
TABLES = [
    "campaigns", "campaign_upload_mode", "leads_temp", "leads", "lead_activities",
    "campaign_leads", "sdrs", "campaign_icps", "icps", "companies_process",
    "campaign_company_campaign_map", "campaign_companies", "crm_data", "api_info"
]

@app.on_event("startup")
def preload_all_tenant_tables():
    with engine.connect() as conn:
        schemas = [row[0] for row in conn.execute(text("SELECT schema_name FROM public.user_directory"))]
    table_names = [
        "campaigns", "campaign_upload_mode", "leads_temp", "leads", "lead_activities",
        "campaign_leads", "sdrs", "campaign_icps", "icps", "companies_process",
        "campaign_company_campaign_map", "campaign_companies", "crm_data", "api_info"
    ]
    for schema in schemas:
        for table in table_names:
            try:
                get_table(table, schema, engine)
            except Exception as e:
                print(f"Failed to preload {table} in schema {schema}: {e}")

app.include_router(auth_router)
app.include_router(api_info_router)
app.include_router(campaign_router)
app.include_router(campaign_company_router)
app.include_router(leads_router)
app.include_router(icps_router)
app.include_router(sdrs_router)
app.include_router(users_router)
# app.include_router(webhook_router)
app.include_router(ai_coaching_router)

# scheduler = AsyncIOScheduler()

# async def run_midnight_batch_processing():
#     try:
#         await run_multi_tenant_batch(process_midnight_batch)
#     except Exception as e:
#         logger.error(f"Error in midnight batch processing: {str(e)}")

# async def run_timeline_bounce_batch():
#     try:
#         await run_multi_tenant_batch(timeline_bounce_job)
#     except Exception as e:
#         logger.error(f"Error in timeline bounce batch: {str(e)}")

# scheduler.add_job(
#     run_midnight_batch_processing,
#     CronTrigger(hour="0", minute="0"),
#     id="midnight_batch_processing",
#     name="Process midnight batch for all campaigns",
#     replace_existing=True
# )

# scheduler.add_job(
#     run_timeline_bounce_batch,
#     CronTrigger(hour="1", minute="0"),
#     id="timeline_bounce_batch",
#     name="Process timeline-based bounces for all campaigns",
#     replace_existing=True
# )

# @app.on_event("startup")
# async def start_scheduler():
#     scheduler.start()

# @app.on_event("shutdown")
# async def shutdown_scheduler():
#     scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 