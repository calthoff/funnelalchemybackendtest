from sqlalchemy import text
from app.db import Base, engine
from app.models.users import User
from app.models.icps import ICP
from app.models.sdrs import SDR
from app.models.prospects import Prospect
from app.models.personas import Persona
from app.models.high_intent_triggers import HighIntentTrigger
from app.models.high_intent_events import HighIntentEvent
from app.models.prospect_activities import ProspectActivity
from app.models.prospect_score_history import ProspectScoreHistory
from app.models.scoring_weights import ScoringWeight
from app.models.notifications import Notification
from app.models.companies import Company
from app.models.company_description import CompanyDescription

def create_company_schema(engine, schema_name: str):

    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            conn.commit()

        models = [
            ICP, SDR, User, Prospect, Persona, HighIntentTrigger, HighIntentEvent,
            ProspectActivity, ProspectScoreHistory, ScoringWeight, Notification, Company, CompanyDescription
        ]

        original_schemas = {}
        for model in models:
            if hasattr(model, '__table__'):
                original_schemas[model] = getattr(model.__table__, 'schema', None)
                model.__table__.schema = schema_name

        Base.metadata.create_all(bind=engine)

        for model in models:
            if hasattr(model, '__table__'):
                model.__table__.schema = original_schemas.get(model, None)
        
        return True
        
    except Exception as e:
        for model in models:
            if hasattr(model, '__table__'):
                model.__table__.schema = original_schemas.get(model, None)
        raise e 