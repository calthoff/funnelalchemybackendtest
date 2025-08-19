import os
import requests
import random
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.db import get_db
from app.utils.auth import get_current_user
from app.models.users import User
from app.utils.db_utils import get_table
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coresignal-prospects", tags=["coresignal-prospects"], redirect_slashes=False)

class CoreSignalService:
    def __init__(self):
        self.api_key = os.getenv("CORESIGNAL_API_KEY")
        if not self.api_key:
            raise ValueError("CORESIGNAL_API_KEY environment variable is required")
        
        self.base_url = "https://api.coresignal.com"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
    
    def build_search_query(self, icps: List[Dict], personas: List[Dict], company_description: Dict) -> Dict[str, Any]:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "nested": {
                                            "path": "experience",
                                            "query": {
                                                "bool": {
                                                    "must": [
                                                        {
                                                            "term": {
                                                                "experience.active_experience": 1
                                                            }
                                                        }
                                                    ],
                                                    "filter": []
                                                }
                                            }
                                        }
                                    }
                                ],
                                "minimum_should_match": 1
                            }
                        }
                    ],
                    "filter": []
                }
            }
        }
        
        experience_must = query["query"]["bool"]["must"][0]["bool"]["should"][0]["nested"]["query"]["bool"]["must"]
        experience_filter = query["query"]["bool"]["must"][0]["bool"]["should"][0]["nested"]["query"]["bool"]["filter"]
        
        if icps and len(icps) > 0:
            icp = icps[0]
            
            if icp.get('industries'):
                industries = list(icp['industries'].values()) if isinstance(icp['industries'], dict) else icp['industries']
                if industries:
                    industry_conditions = []
                    for industry in industries:
                        industry_conditions.extend([
                            {
                                "match": {
                                    "experience.company_industry": industry
                                }
                            },
                            {
                                "query_string": {
                                    "query": industry,
                                    "default_field": "experience.company_categories_and_keywords"
                                }
                            }
                        ])
                    experience_filter.append({
                        "bool": {
                            "should": industry_conditions,
                            "minimum_should_match": 1
                        }
                    })
            
            if icp.get('employee_size_range'):
                size_range = icp['employee_size_range']
                if isinstance(size_range, dict):
                    min_size = size_range.get('min', 0)
                    max_size = size_range.get('max', 100000)
                    experience_filter.append({
                        "range": {
                            "experience.company_employees_count": {
                                "gte": min_size,
                                "lte": max_size
                            }
                        }
                    })
            
            if icp.get('location'):
                locations = list(icp['location'].values()) if isinstance(icp['location'], dict) else icp['location']
                if locations:
                    location_conditions = []
                    for location in locations:
                        location_conditions.append({
                            "match": {
                                "experience.company_hq_full_address": location
                            }
                        })
                    experience_filter.append({
                        "bool": {
                            "should": location_conditions,
                            "minimum_should_match": 1
                        }
                    })
        
        if personas and len(personas) > 0:
            persona = personas[0]
            
            if persona.get('title_keywords'):
                titles = list(persona['title_keywords'].values()) if isinstance(persona['title_keywords'], dict) else persona['title_keywords']
                if titles:
                    title_query = " OR ".join([f'"{title}"' for title in titles])
                    experience_filter.append({
                        "query_string": {
                            "query": title_query,
                            "default_field": "experience.position_title"
                        }
                    })
            
            if persona.get('seniority_levels'):
                seniority = list(persona['seniority_levels'].values()) if isinstance(persona['seniority_levels'], dict) else persona['seniority_levels']
                if seniority:
                    seniority_conditions = []
                    for level in seniority:
                        seniority_conditions.append({
                            "match": {
                                "experience.management_level": level
                            }
                        })
                    experience_filter.append({
                        "bool": {
                            "should": seniority_conditions,
                            "minimum_should_match": 1
                        }
                    })
            
            if persona.get('departments'):
                departments = list(persona['departments'].values()) if isinstance(persona['departments'], dict) else persona['departments']
                if departments:
                    department_conditions = []
                    for dept in departments:
                        department_conditions.append({
                            "match": {
                                "experience.department": dept
                            }
                        })
                    experience_filter.append({
                        "bool": {
                            "should": department_conditions,
                            "minimum_should_match": 1
                        }
                    })
        
        query["query"]["bool"]["filter"].append({
            "term": {
                "is_decision_maker": 1
            }
        })
        
        return query
    
    async def search_prospects(self, icps: List[Dict], personas: List[Dict], company_description: Dict, limit: int = 20) -> List[Dict]:
        try:
            query = self.build_search_query(icps, personas, company_description)
            
            logger.info(f"CoreSignal Search Query: {query}")
            logger.info(f"CoreSignal Headers: {self.headers}")
            
            response = requests.post(
                f"{self.base_url}/cdapi/v2/employee_multi_source/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"CoreSignal API error: {response.status_code} - {response.text}")
                raise Exception(f"CoreSignal API returned {response.status_code}: {response.text}")
            
            data = response.json()
            prospect_ids = data if isinstance(data, list) else []
            logger.info(f"Found {len(prospect_ids)} prospect IDs from CoreSignal API")
            
            if len(prospect_ids) > limit:
                selected_prospect_ids = random.sample(prospect_ids, limit)
            else:
                selected_prospect_ids = prospect_ids
            
            transformed_prospects = []
            for prospect_id in selected_prospect_ids:
                try:
                    prospect_data = await self.get_prospect_details(prospect_id)
                    if prospect_data:
                        transformed_prospect = self.transform_prospect_data(prospect_data)
                        transformed_prospects.append(transformed_prospect)
                except Exception as e:
                    logger.warning(f"Failed to get details for prospect {prospect_id}: {str(e)}")
                    continue
            
            logger.info(f"Successfully transformed {len(transformed_prospects)} prospects from CoreSignal")
            return transformed_prospects
            
        except Exception as e:
            logger.error(f"Error searching CoreSignal prospects: {str(e)}")
            raise Exception(f"Failed to search CoreSignal prospects: {str(e)}")
    
    async def get_prospect_details(self, prospect_id: int) -> Optional[Dict]:
        try:
            response = requests.get(
                f"{self.base_url}/cdapi/v2/employee_multi_source/collect/{prospect_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"CoreSignal prospect details error: {response.status_code} - {response.text}")
                return None
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting prospect details for {prospect_id}: {str(e)}")
            return None
    
    def transform_prospect_data(self, prospect_data: Dict) -> Dict:
        active_experience = None
        for exp in prospect_data.get('experience', []):
            if exp.get('active_experience') == 1:
                active_experience = exp
                break
        
        if not active_experience:
            active_experience = prospect_data.get('experience', [{}])[0] if prospect_data.get('experience') else {}
        
        transformed_prospect = {
            'first_name': prospect_data.get('first_name', ''),
            'last_name': prospect_data.get('last_name', ''),
            'email': prospect_data.get('primary_professional_email', ''),
            'company_name': active_experience.get('company_name', ''),
            'job_title': active_experience.get('position_title', ''),
            'linkedin_url': prospect_data.get('linkedin_url', ''),
            'phone_number': '',
            'location': prospect_data.get('location_country', ''),
            'department': active_experience.get('department', ''),
            'seniority': active_experience.get('management_level', ''),
            'source': 'coresignal',
            'source_id': str(prospect_data.get('id', '')),
            'headshot_url': prospect_data.get('picture_url', ''),
            'coresignal_data': {
                'industry': active_experience.get('company_industry', ''),
                'company_size': active_experience.get('company_employees_count', ''),
                'company_revenue': active_experience.get('company_annual_revenue_source_1', ''),
                'technology_stack': prospect_data.get('inferred_skills', []),
                'location_country': prospect_data.get('location_country', ''),
                'location_region': active_experience.get('company_hq_country', ''),
                'skills': prospect_data.get('inferred_skills', []),
                'experience': [exp.get('position_title', '') for exp in prospect_data.get('experience', [])],
                'education': [edu.get('institution_name', '') for edu in prospect_data.get('education', [])]
            }
        }
        
        return transformed_prospect
    
    async def enrich_prospect(self, email: str) -> Optional[Dict]:
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "primary_professional_email": email
                                }
                            }
                        ]
                    }
                }
            }
            
            response = requests.post(
                f"{self.base_url}/cdapi/v2/employee_multi_source/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"CoreSignal enrichment error: {response.status_code} - {response.text}")
                raise Exception(f"CoreSignal enrichment failed: {response.status_code} - {response.text}")
            
            data = response.json()
            prospect_ids = data if isinstance(data, list) else []
            
            if prospect_ids:
                return await self.get_prospect_details(prospect_ids[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error enriching prospect {email}: {str(e)}")
            raise Exception(f"Failed to enrich prospect {email}: {str(e)}")
    
    def get_company_info(self, company_name: str) -> Optional[Dict]:
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "nested": {
                                    "path": "experience",
                                    "query": {
                                        "bool": {
                                            "must": [
                                                {
                                                    "match": {
                                                        "experience.company_name": company_name
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
            
            response = requests.post(
                f"{self.base_url}/cdapi/v2/employee_multi_source/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"CoreSignal company search error: {response.status_code} - {response.text}")
                raise Exception(f"CoreSignal company search failed: {response.status_code} - {response.text}")
            
            data = response.json()
            prospect_ids = data if isinstance(data, list) else []
            
            if prospect_ids:
                return self.get_prospect_details(prospect_ids[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting company info for {company_name}: {str(e)}")
            raise Exception(f"Failed to get company info for {company_name}: {str(e)}")

@router.post("/search")
async def search_coresignal_prospects(
    limit: int = 2,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        company_table = get_table('icps', current_user.schema_name, db.bind)
        persona_table = get_table('personas', current_user.schema_name, db.bind)
        company_description_table = get_table('company_descriptions', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            icps_result = conn.execute(company_table.select())
            icps = [dict(row._mapping) for row in icps_result.fetchall()]
            personas_result = conn.execute(persona_table.select())
            personas = [dict(row._mapping) for row in personas_result.fetchall()]
            company_description_result = conn.execute(company_description_table.select())
            company_description = company_description_result.fetchone()
            company_description_dict = dict(company_description._mapping) if company_description else {}
        
        if not icps and not personas:
            raise HTTPException(
                status_code=400, 
                detail="Please configure company profiles and personas before searching for prospects"
            )
        
        try:
            coresignal_service = CoreSignalService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="CoreSignal API key not configured. Please set CORESIGNAL_API_KEY environment variable."
            )
        
        prospects = await coresignal_service.search_prospects(
            icps=icps,
            personas=personas,
            company_description=company_description_dict,
            limit=limit
        )
        
        return {
            "prospects": prospects,
            "total_found": len(prospects),
            "search_criteria": {
                "icps_count": len(icps),
                "personas_count": len(personas),
                "has_company_description": bool(company_description_dict)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching CoreSignal prospects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search prospects: {str(e)}")

@router.post("/enrich")
async def enrich_prospect(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        try:
            coresignal_service = CoreSignalService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="CoreSignal API key not configured. Please set CORESIGNAL_API_KEY environment variable."
            )
        enriched_data = await coresignal_service.enrich_prospect(email)
        
        if not enriched_data:
            raise HTTPException(status_code=404, detail="Prospect not found or could not be enriched")
        
        return enriched_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enriching prospect {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enrich prospect: {str(e)}")

@router.get("/company/{company_name}")
async def get_company_info(
    company_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        try:
            coresignal_service = CoreSignalService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="CoreSignal API key not configured. Please set CORESIGNAL_API_KEY environment variable."
            )
        company_info = coresignal_service.get_company_info(company_name)
        
        if not company_info:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return company_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company info for {company_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get company info: {str(e)}")

@router.post("/import")
async def import_coresignal_prospects(
    prospect_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        try:
            coresignal_service = CoreSignalService()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="CoreSignal API key not configured. Please set CORESIGNAL_API_KEY environment variable."
            )
        
        prospect_table = get_table('prospects', current_user.schema_name, db.bind)
        sdr_table = get_table('sdrs', current_user.schema_name, db.bind)
        
        with db.bind.connect() as conn:
            all_sdrs = conn.execute(sdr_table.select()).fetchall()
            
            last_prospect = conn.execute(
                prospect_table.select().order_by(prospect_table.c.created_at.desc())
            ).fetchone()

        imported_prospects = []
        skipped_prospects = []
        
        for prospect_id in prospect_ids:
            try:
                existing_prospect = conn.execute(
                    prospect_table.select().where(prospect_table.c.source_id == prospect_id)
                ).fetchone()
                
                if existing_prospect:
                    skipped_prospects.append(prospect_id)
                    continue
            except Exception as e:
                logger.error(f"Error importing prospect {prospect_id}: {str(e)}")
                skipped_prospects.append(prospect_id)
        
        return {
            "imported": len(imported_prospects),
            "skipped": len(skipped_prospects),
            "imported_prospects": imported_prospects,
            "skipped_prospect_ids": skipped_prospects
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CoreSignal prospects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import prospects: {str(e)}") 