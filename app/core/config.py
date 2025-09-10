from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Base
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Dashboard API"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    FERNET_SECRET_KEY: Optional[str] = None
    
    # Database
    DATABASE_URL: str

    # SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "lauren@funnelalchemyhq.com"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # PDL
    PDL_API_KEY: Optional[str] = None

    # SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_FROM: Optional[str] = None

    # AWS Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: Optional[str] = None

    # PostgreSQL Configuration for Funnel Prospects
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[str] = None
    POSTGRES_DBNAME: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_REGION: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 