import os
import asyncio
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import PDL, but handle gracefully if not available
try:
    from peopledatalabs import PDLPY
    PDL_AVAILABLE = True
except ImportError:
    PDL_AVAILABLE = False
    logger.warning("peopledatalabs package not available. Using mock PDL service.")

class MockPDLClient:
    """Mock PDL client for when the real package is not available"""
    
    def __init__(self, api_key):
        self.api_key = api_key
    
    def person(self):
        return self
    
    def search(self, **kwargs):
        # Return mock response
        return MockResponse({
            'data': [
                {
                    'id': 'mock_1',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'email': 'john.doe@example.com',
                    'job_title': 'Software Engineer',
                    'company': {'name': 'Tech Corp'},
                    'location_name': 'San Francisco, CA'
                },
                {
                    'id': 'mock_2',
                    'first_name': 'Jane',
                    'last_name': 'Smith',
                    'email': 'jane.smith@example.com',
                    'job_title': 'Product Manager',
                    'company': {'name': 'Startup Inc'},
                    'location_name': 'New York, NY'
                }
            ],
            'total': 2
        })

class MockResponse:
    """Mock response object"""
    
    def __init__(self, data):
        self.data = data
        self.status_code = 200
    
    def json(self):
        return self.data

class PDLService:
    def __init__(self):
        self.api_key = os.getenv("PDL_API_KEY")
        if not self.api_key:
            raise ValueError("PDL_API_KEY environment variable is required")
        
        if PDL_AVAILABLE:
            self.client = PDLPY(api_key=self.api_key)
        else:
            self.client = MockPDLClient(self.api_key)
    
    def build_search_query(self, icps: List[Dict], personas: List[Dict], company_description: Dict) -> Dict[str, Any]:
        query = {
            "sql": "",
            "size": 100,
            "pretty": True
        }
        sql_conditions = []
        if icps:
            company_conditions = []
            for icp in icps:
                if icp.get('industries'):
                    industries = list(icp['industries'].values()) if isinstance(icp['industries'], dict) else icp['industries']
                    if industries:
                        industry_list = "', '".join(industries)
                        company_conditions.append(f"company.industry IN ('{industry_list}')")
                if icp.get('employee_size_range'):
                    size_range = icp['employee_size_range']
                    if isinstance(size_range, dict):
                        min_size = size_range.get('min', 0)
                        max_size = size_range.get('max', 100000)
                        company_conditions.append(f"company.employee_count BETWEEN {min_size} AND {max_size}")
                if icp.get('arr_range'):
                    arr_range = icp['arr_range']
                    if isinstance(arr_range, dict):
                        min_arr = arr_range.get('min', 0) * 1000000
                        max_arr = arr_range.get('max', 1000000000) * 1000000
                        company_conditions.append(f"company.revenue BETWEEN {min_arr} AND {max_arr}")
                
                if icp.get('location'):
                    locations = list(icp['location'].values()) if isinstance(icp['location'], dict) else icp['location']
                    if locations:
                        location_list = "', '".join(locations)
                        company_conditions.append(f"location_name IN ('{location_list}')")
            
            if company_conditions:
                sql_conditions.append(f"({' OR '.join(company_conditions)})")
        
        if personas:
            persona_conditions = []
            for persona in personas:
                if persona.get('title_keywords'):
                    titles = list(persona['title_keywords'].values()) if isinstance(persona['title_keywords'], dict) else persona['title_keywords']
                    if titles:
                        title_conditions = []
                        for title in titles:
                            title_conditions.append(f"job_title ILIKE '%{title}%'")
                        persona_conditions.append(f"({' OR '.join(title_conditions)})")
                
                if persona.get('departments'):
                    departments = list(persona['departments'].values()) if isinstance(persona['departments'], dict) else persona['departments']
                    if departments:
                        dept_list = "', '".join(departments)
                        persona_conditions.append(f"job_title_level IN ('{dept_list}')")
                
                if persona.get('seniority_levels'):
                    seniority = list(persona['seniority_levels'].values()) if isinstance(persona['seniority_levels'], dict) else persona['seniority_levels']
                    if seniority:
                        seniority_list = "', '".join(seniority)
                        persona_conditions.append(f"seniority IN ('{seniority_list}')")
            
            if persona_conditions:
                sql_conditions.append(f"({' OR '.join(persona_conditions)})")
        
        sql_conditions.extend([
            "email IS NOT NULL",
            "email != ''",
            "first_name IS NOT NULL",
            "last_name IS NOT NULL",
            "company.name IS NOT NULL"
        ])
        
        if company_description and company_description.get('exclusion_criteria'):
            pass
        
        if sql_conditions:
            query["sql"] = " AND ".join(sql_conditions)
        
        return query
    
    async def search_prospects(self, icps: List[Dict], personas: List[Dict], company_description: Dict, limit: int = 100) -> List[Dict]:
        try:
            query = self.build_search_query(icps, personas, company_description)
            query["size"] = min(limit, 100)
            
            logger.info(f"PDL Search Query: {query}")
            
            response = self.client.person.search(**query)
            
            if response.status_code != 200:
                logger.error(f"PDL API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            prospects = data.get('data', [])
            
            transformed_prospects = []
            for prospect in prospects:
                transformed_prospect = {
                    'first_name': prospect.get('first_name', ''),
                    'last_name': prospect.get('last_name', ''),
                    'email': prospect.get('email', ''),
                    'company_name': prospect.get('job_company_name', ''),
                    'job_title': prospect.get('job_title', ''),
                    'linkedin_url': prospect.get('linkedin_url', ''),
                    'phone_number': prospect.get('phone_number', ''),
                    'location': prospect.get('location_name', ''),
                    'department': prospect.get('job_title_level', ''),
                    'seniority': prospect.get('seniority', ''),
                    'source': 'pdl',
                    'source_id': prospect.get('id', ''),
                    'headshot_url': prospect.get('profile_pic_url', ''),
                    'pdl_data': {
                        'industry': prospect.get('job_company_industry', ''),
                        'company_size': prospect.get('job_company_size', ''),
                        'company_revenue': prospect.get('job_company_revenue', ''),
                        'location_country': prospect.get('location_country', ''),
                        'location_region': prospect.get('location_region', ''),
                        'skills': prospect.get('skills', []),
                        'experience': prospect.get('experience', []),
                        'education': prospect.get('education', [])
                    }
                }
                transformed_prospects.append(transformed_prospect)
            
            logger.info(f"Found {len(transformed_prospects)} prospects from PDL")
            return transformed_prospects
            
        except Exception as e:
            logger.error(f"Error searching PDL prospects: {str(e)}")
            return []
    
    async def enrich_prospect(self, email: str) -> Optional[Dict]:
        try:
            response = self.client.person.enrichment(email=email)
            
            if response.status_code != 200:
                logger.error(f"PDL enrichment error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"Error enriching prospect {email}: {str(e)}")
            return None
    
    def get_company_info(self, company_name: str) -> Optional[Dict]:
        try:
            response = self.client.company.enrichment(name=company_name)
            
            if response.status_code != 200:
                logger.error(f"PDL company enrichment error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"Error getting company info for {company_name}: {str(e)}")
            return None 