from sqlalchemy import text
from app.db import Base, engine
from app.models.companies import Company
from app.models.users import User
from app.models.products import Product
from app.models.leads import Lead
from app.models.leads_temp import LeadTemp
from app.models.campaigns import Campaign
from app.models.campaign_leads import CampaignLead
from app.models.lead_activities import LeadActivity
from app.models.icps import ICP
from app.models.campaign_icps import CampaignICP
from app.models.campaign_managers import CampaignManager
from app.models.lead_handlers import LeadHandler
from app.models.crm_data import CRMData
from app.models.api_info import APIInfo
from app.models.campaign_companies import CampaignCompany
from app.models.sdr_msg import SDRMsg
from app.models.companies_process import CompaniesProcess
from app.models.lead_process import LeadProcess
from app.models.log import Log
from app.models.campaign_company_campaign_map import CampaignCompanyCampaignMap
from app.models.sdrs import SDR
from app.models.campaign_upload_mode import CampaignUploadMode

def create_company_schema(engine, schema_name: str):

    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            conn.commit()

        models = [
            Company, User, Product, Lead, LeadTemp, Campaign, CampaignLead,
            LeadActivity, ICP, CampaignICP, CampaignManager, LeadHandler,
            CRMData, APIInfo, CampaignCompany, SDRMsg,
            CompaniesProcess, Log, CampaignCompanyCampaignMap,
            LeadProcess, SDR, CampaignUploadMode
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