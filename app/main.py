from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .db import Base, engine
import sqlalchemy
from .api.auth import router as auth_router
from app.models.user_directory import UserDirectory
from app.api.sdrs import router as sdrs_router
from app.api.users import router as users_router
from app.api.icps import router as icps_router
from app.api.personas import router as personas_router
from app.api.notifications import router as notifications_router
from app.api.prospects import router as prospects_router, score_prospect_background
from app.api.scoring_weights import router as scoring_weights_router
from app.api.company_description import router as company_description_router
from app.api.calibration import router as calibration_router
from app.api.coresignal_prospects import router as coresignal_prospects_router
import os
import logging
from dotenv import load_dotenv
import asyncio
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.utils.db_utils import get_table

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

if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

origins = [
    "https://funnelalchemy.onrender.com",
    "https://funnel-alchemy-production.up.railway.app",
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

background_scoring_running = False
background_thread = None

async def periodic_score_update():
    global background_scoring_running
    
    while background_scoring_running:
        try:
            logger.info("🔄 Starting periodic score update...")
            
            with engine.connect() as conn:
                schemas = [row[0] for row in conn.execute(text("SELECT schema_name FROM public.user_directory"))]
            
            for schema in schemas:
                try:
                    prospect_table = get_table('prospects', schema, engine)
                    
                    with engine.connect() as conn:
                        prospects_to_score = conn.execute(
                            prospect_table.select().where(
                                (prospect_table.c.current_score == -1) |
                                (prospect_table.c.score_reason == 'Generating...')
                            ).limit(10)
                        ).fetchall()
                    
                    logger.info(f"📊 Found {len(prospects_to_score)} prospects to score in schema {schema}")
                    
                    for prospect in prospects_to_score:
                        try:
                            await score_prospect_background(str(prospect.id), schema)
                            # Small delay to avoid overwhelming the API
                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.error(f"Error scoring prospect {prospect.id}: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Error processing schema {schema}: {e}")
                    continue
            
            logger.info("✅ Periodic score update completed")
            
        except Exception as e:
            logger.error(f"Error in periodic score update: {e}")
        
        await asyncio.sleep(900)

def start_background_scoring():
    """Start the background scoring thread"""
    global background_scoring_running, background_thread
    
    if not background_scoring_running:
        background_scoring_running = True
        background_thread = threading.Thread(target=lambda: asyncio.run(periodic_score_update()))
        background_thread.daemon = True
        background_thread.start()
        logger.info("🚀 Background scoring started")

def stop_background_scoring():
    """Stop the background scoring thread"""
    global background_scoring_running
    background_scoring_running = False
    logger.info("🛑 Background scoring stopped")

@app.on_event("startup")
async def startup_event():
    """Start background scoring on startup"""
    start_background_scoring()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scoring on shutdown"""
    stop_background_scoring()

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

@app.get("/background-scoring-status")
async def get_background_scoring_status():
    """Check if background scoring is running"""
    return {
        "background_scoring_running": background_scoring_running,
        "status": "running" if background_scoring_running else "stopped"
    }

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
    "icps", "sdrs", "prospects", "personas", "high_intent_triggers",
    "high_intent_events", "prospect_activities", "prospect_score_history",
    "scoring_weights", "notifications", "companies"
]

@app.on_event("startup")
def preload_all_tenant_tables():
    with engine.connect() as conn:
        schemas = [row[0] for row in conn.execute(text("SELECT schema_name FROM public.user_directory"))]
    for schema in schemas:
        for table in TABLES:
            try:
                get_table(table, schema, engine)
            except Exception as e:
                print(f"Failed to preload {table} in schema {schema}: {e}")

app.include_router(auth_router)
app.include_router(sdrs_router)
app.include_router(users_router)
app.include_router(icps_router)
app.include_router(personas_router)
app.include_router(notifications_router)
app.include_router(prospects_router)
app.include_router(scoring_weights_router)
app.include_router(company_description_router)
app.include_router(calibration_router)
app.include_router(coresignal_prospects_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 