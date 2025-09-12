import os
import sys
import asyncio
import json
import requests
import random
from typing import List, Dict, Any, Optional

class CoreSignalService:
    def __init__(self):
        self.api_key = 'oxBN1X7gc2ThK3jNSSHCON0oILDZ4wp5'
        self.base_url = "https://api.coresignal.com"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
    
    def build_search_query(self, company_profiles: List[Dict], personas: List[Dict], company_description: Dict) -> Dict[str, Any]:
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
                                                "term": {
                                                    "experience.active_experience": 1
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
        
        nested_must = query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["must"]
        
        icp = company_profiles[0] if company_profiles and len(company_profiles) > 0 else {}
        persona = personas[0] if personas and len(personas) > 0 else {}
        
        if persona.get('position_title'):
            titles = persona['position_title'] if isinstance(persona['position_title'], list) else []
            if titles:
                if len(titles) == 1:
                    query["query"]["bool"]["must"].insert(0, {
                        "match_phrase": {
                            "active_experience_title": titles[0]
                        }
                    })
                else:
                    nested_must.append({
                        "bool": {
                            "should": [
                                {
                                    "match_phrase": {
                                        "experience.position_title": title
                                    }
                                } for title in titles
                            ],
                            "minimum_should_match": 1
                        }
                    })
        
        if persona.get('seniority_levels'):
            seniority_levels = persona['seniority_levels'] if isinstance(persona['seniority_levels'], list) else []
            if seniority_levels:
                if len(seniority_levels) == 1:
                    nested_must.append({
                        "match_phrase": {
                            "experience.management_level": seniority_levels[0]
                        }
                    })
                else:
                    nested_must.append({
                        "terms": {
                            "experience.management_level.exact": seniority_levels
                        }
                    })
        
        if company_description and company_description.get('description'):
            description = company_description['description']
            nested_must.append({
                "query_string": {
                    "query": description,
                    "default_field": "experience.company_categories_and_keywords",
                    "default_operator": "AND"
                }
            })
        
        if icp.get('industries'):
            industries = icp['industries'] if isinstance(icp['industries'], list) else []
            if industries:
                if len(industries) == 1:
                    nested_must.append({
                        "match": {
                            "experience.company_industry": industries[0]
                        }
                    })
                else:
                    expanded_queries = []
                    for industry in industries:
                        expanded_query = self._expand_industry_keywords(industry)
                        expanded_queries.append(expanded_query)
                    
                    combined_query = " OR ".join(expanded_queries)
                    
                    nested_must.append({
                        "bool": {
                            "should": [
                                {
                                    "query_string": {
                                        "query": combined_query,
                                        "default_field": "experience.company_categories_and_keywords",
                                        "default_operator": "OR"
                                    }
                                },
                                {
                                    "query_string": {
                                        "query": combined_query,
                                        "default_field": "experience.company_industry",
                                        "default_operator": "OR"
                                    }
                                }
                            ],
                            "minimum_should_match": 1
                        }
                    })
        
        if icp.get('location'):
            locations = icp['location'] if isinstance(icp['location'], list) else []
            if locations:
                location = locations[0]
                if self._is_city(location):
                    nested_must.append({
                        "match": {
                            "experience.company_hq_city": location
                        }
                    })
                else:
                    nested_must.append({
                        "term": {
                            "experience.company_hq_country": location
                        }
                    })
        
        if icp.get('employee_size_range'):
            size_ranges = icp['employee_size_range'] if isinstance(icp['employee_size_range'], list) else []
            if size_ranges:
                min_size = float('inf')
                max_size = 0
                
                for size_range in size_ranges:
                    if "-" in str(size_range):
                        parts = str(size_range).split("-")
                        if len(parts) == 2:
                            try:
                                range_min = int(parts[0])
                                range_max = int(parts[1])
                                min_size = min(min_size, range_min)
                                max_size = max(max_size, range_max)
                            except ValueError:
                                continue
                    elif str(size_range).endswith("+"):
                        try:
                            min_size = min(min_size, int(str(size_range).replace("+", "")))
                            max_size = float('inf')
                        except ValueError:
                            continue
                
                if min_size != float('inf'):
                    range_filter = {
                        "range": {
                            "experience.company_employees_count": {
                                "gte": min_size
                            }
                        }
                    }
                    if max_size != float('inf'):
                        range_filter["range"]["experience.company_employees_count"]["lte"] = max_size
                    
                    nested_must.append(range_filter)

        if icp.get('revenue_range'):
            revenue_ranges = icp['revenue_range'] if isinstance(icp['revenue_range'], list) else []
            if revenue_ranges:
                min_revenue = float('inf')
                max_revenue = 0
                
                for revenue_range in revenue_ranges:
                    if "-" in str(revenue_range):
                        parts = str(revenue_range).split("-")
                        if len(parts) == 2:
                            try:
                                min_val = parts[0].replace("M", "").replace("$", "").strip()
                                max_val = parts[1].replace("M", "").replace("$", "").strip()
                                min_revenue = min(min_revenue, int(min_val) * 1000000)
                                max_revenue = max(max_revenue, int(max_val) * 1000000)
                            except ValueError:
                                continue
                    elif str(revenue_range).endswith("+"):
                        try:
                            val = str(revenue_range).replace("+", "").replace("M", "").replace("$", "").strip()
                            min_revenue = min(min_revenue, int(val) * 1000000)
                            max_revenue = float('inf')
                        except ValueError:
                            continue
                
                if min_revenue != float('inf'):
                    range_filter = {
                        "bool": {
                            "should": [
                                {
                                    "range": {
                                        "experience.company_annual_revenue_source_1": {
                                            "gte": min_revenue
                                        }
                                    }
                                },
                                {
                                    "range": {
                                        "experience.company_annual_revenue_source_5": {
                                            "gte": min_revenue
                                        }
                                    }
                                }
                            ],
                            "minimum_should_match": 1
                        }
                    }
                    
                    if max_revenue != float('inf'):
                        range_filter["bool"]["should"][0]["range"]["experience.company_annual_revenue_source_1"]["lte"] = max_revenue
                        range_filter["bool"]["should"][1]["range"]["experience.company_annual_revenue_source_5"]["lte"] = max_revenue
                    
                    nested_must.append(range_filter)
        
        return query
    
    def _expand_industry_keywords(self, industry: str) -> str:
        industry_lower = industry.lower().strip()
        
        industry_abbreviations = {
            'saas': ['saas', 'software as a service'],
            'ai': ['ai', 'artificial intelligence'],
            'fintech': ['fintech', 'financial technology'],
            'healthtech': ['healthtech', 'health technology'],
            'edtech': ['edtech', 'education technology'],
            'cybersecurity': ['cybersecurity', 'cyber security'],
            'blockchain': ['blockchain', 'cryptocurrency'],
            'ecommerce': ['ecommerce', 'e-commerce'],
            'biotech': ['biotech', 'biotechnology'],
            'cleantech': ['cleantech', 'clean technology'],
            'martech': ['martech', 'marketing technology'],
            'hrtech': ['hrtech', 'hr technology'],
            'proptech': ['proptech', 'property technology'],
            'agtech': ['agtech', 'agricultural technology'],
            'telecom': ['telecom', 'telecommunications'],
            'ml': ['ml', 'machine learning'],
            'iot': ['iot', 'internet of things'],
            'vr': ['vr', 'virtual reality'],
            'ar': ['ar', 'augmented reality'],
            'api': ['api', 'application programming interface'],
            'crm': ['crm', 'customer relationship management'],
            'erp': ['erp', 'enterprise resource planning'],
            'hr': ['hr', 'human resources'],
            'it': ['it', 'information technology'],
            'ui': ['ui', 'user interface'],
            'ux': ['ux', 'user experience'],
            'seo': ['seo', 'search engine optimization'],
            'sem': ['sem', 'search engine marketing'],
            'ppc': ['ppc', 'pay per click'],
            'cpa': ['cpa', 'cost per acquisition'],
            'roi': ['roi', 'return on investment'],
            'kpi': ['kpi', 'key performance indicator'],
            'b2b': ['b2b', 'business to business'],
            'b2c': ['b2c', 'business to consumer'],
            'paas': ['paas', 'platform as a service'],
            'iaas': ['iaas', 'infrastructure as a service']
        }
        
        if industry_lower in industry_abbreviations:
            variations = industry_abbreviations[industry_lower]
            return ' OR '.join([f'"{var}"' for var in variations])
        
        return f'"{industry}"'
    
    def _is_city(self, location: str) -> bool:
        countries = {
            'United States', 'USA', 'US', 'Canada', 'United Kingdom', 'UK', 'Germany', 
            'France', 'Italy', 'Spain', 'Netherlands', 'Belgium', 'Switzerland', 
            'Austria', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Poland', 'Japan', 
            'China', 'India', 'Singapore', 'Australia', 'New Zealand', 
            'Brazil', 'Mexico', 'Argentina', 'Chile', 'Colombia', 'South Africa', 
            'Nigeria', 'Kenya', 'Egypt', 'Morocco', 'Tunisia', 'Russia', 'Ukraine', 
            'Belarus', 'Kazakhstan', 'Turkey', 'Israel', 'Saudi Arabia', 'UAE', 
            'Qatar', 'Kuwait', 'Bahrain', 'Thailand', 'Vietnam', 'Malaysia', 
            'Indonesia', 'Philippines', 'Taiwan', 'Hong Kong', 'Macau'
        }
        return location not in countries
    
    async def search_prospects(self, company_profiles: List[Dict], personas: List[Dict], company_description: Dict, limit: int) -> List[Dict]:
        try:
            query = self.build_search_query(company_profiles, personas, company_description)
            
            print(f"CoreSignal Search Query: {query}")
            print(f"CoreSignal Headers: {self.headers}")
            
            response = requests.post(
                f"{self.base_url}/cdapi/v2/employee_multi_source/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"CoreSignal API error: {response.status_code} - {response.text}")
                raise Exception(f"CoreSignal API returned {response.status_code}: {response.text}")
            
            data = response.json()
            prospect_ids = data if isinstance(data, list) else []
            print(f"Found {len(prospect_ids)} prospect IDs from CoreSignal API")
            print(f"Prospect IDs: {prospect_ids}")
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
                    print(f"Failed to get details for prospect {prospect_id}: {str(e)}")
                    continue
            
            print(f"Successfully transformed {len(transformed_prospects)} prospects from CoreSignal")
            return transformed_prospects
            
        except Exception as e:
            print(f"Error searching CoreSignal prospects: {str(e)}")
            raise Exception(f"Failed to search CoreSignal prospects: {str(e)}")
    
    async def get_prospect_details(self, prospect_id: int) -> Optional[Dict]:
        try:
            response = requests.get(
                f"{self.base_url}/cdapi/v2/employee_multi_source/collect/{prospect_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"CoreSignal prospect details error: {response.status_code} - {response.text}")
                return None
            return response.json()
            
        except Exception as e:
            print(f"Error getting prospect details for {prospect_id}: {str(e)}")
            return None
    
    def transform_prospect_data(self, prospect_data: Dict) -> Dict:
        active_experience = None
        for exp in prospect_data.get('experience', []):
            if exp.get('active_experience') == 1:
                active_experience = exp
                break
        
        if not active_experience:
            active_experience = prospect_data.get('experience', [{}])[0] if prospect_data.get('experience') else {}
        
        return prospect_data

def main():
    company_description = {
        'description': '',
        'exclusion_criteria': []
    }
    
    company_profiles = [{
        'industries': ['Higher Education'],
        'employee_size_range': ['500+'],
        'revenue_range': ['50M+'],
        'funding_stages': [],
        'location': ['San Francisco']
    }]
    
    personas = [{
        'position_title': ['CTO', 'CEO'],
        'seniority_levels': ['C-Level', 'VP'],
        'buying_roles': []
    }]
    
    print(f"Company Description: {company_description['description']}")
    print(f"Industries: {company_profiles[0]['industries']}")
    print(f"Employee Ranges: {company_profiles[0]['employee_size_range']}")
    print(f"Revenue Ranges: {company_profiles[0]['revenue_range']}")
    print(f"Title Keywords: {personas[0]['position_title']}")
    print(f"Seniority Levels: {personas[0]['seniority_levels']}")
    print()
    
    # search limit
    limit = 0

    try:
        coresignal_service = CoreSignalService()
        print("Service initialized")
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure to set CORESIGNAL_API_KEY environment variable")
        return
    
    print("Building Search Query")
    try:
        query = coresignal_service.build_search_query(company_profiles=company_profiles, personas=personas, company_description=company_description)
        print("Query built successfully")
        print(f"Query preview: {json.dumps(query, indent=2)[:300]}...")
    except Exception as e:
        print(f"Error building query: {e}")
        return
    print()
    
    print("Calling CoreSignal API")
    try:
        async def search_prospects():
            return await coresignal_service.search_prospects(
                company_profiles=company_profiles,
                personas=personas,
                company_description=company_description,
                limit=limit
            )
        
        prospects = asyncio.run(search_prospects())
        
        print(f"API call successful!")
        print(f"Found {len(prospects)} prospects")
        
        print("\nResults")
        for i, prospect in enumerate(prospects, 1):
            print(f"\nProspect {i}:")
            print(f"  Name: {prospect.get('first_name', '')} {prospect.get('last_name', '')}")
            print(f"  Title: {prospect.get('job_title', '')}")
            print(f"  Company: {prospect.get('company_name', '')}")
            print(f"  Email: {prospect.get('email', '')}")
            print(f"  LinkedIn: {prospect.get('linkedin_url', '')}")
        
        with open("coresignal_results.json", 'w') as f:
            json.dump(prospects, f, indent=2)
        print(f"\nResults saved to: coresignal_results.json")
        
    except Exception as e:
        print(f"Error calling API: {e}")
        return
    
    print("\nExample completed")

if __name__ == "__main__":
    main()
