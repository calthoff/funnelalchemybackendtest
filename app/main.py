from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .db import Base, engine
import sqlalchemy
from .api.auth import router as auth_router
from app.models.users import User
from app.api.users import router as users_router
from app.api.customers import router as customers_router
import os
import logging
from dotenv import load_dotenv

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


def create_tables():
    """Create necessary tables for the application"""
    inspector = sqlalchemy.inspect(engine)
    if not inspector.has_table('users'):
        User.__table__.create(engine, checkfirst=True)
        print("Created users table")
    else:
        print("users table already exists")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    create_tables()

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

@app.get("/")
def root():
    return {"message": "Funnel Alchemy API"}

# Include auth, users, and customers routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(customers_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 