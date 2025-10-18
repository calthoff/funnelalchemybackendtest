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
        
        if company_profiles and len(company_profiles) > 0:
            icp = company_profiles[0]
            
            if icp.get('industries'):
                industries = icp['industries'] if isinstance(icp['industries'], list) else []
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
                size_ranges = icp['employee_size_range'] if isinstance(icp['employee_size_range'], list) else []
                if size_ranges:
                    size_conditions = []
                    for size_range in size_ranges:
                        if "-" in str(size_range):
                            parts = str(size_range).split("-")
                            if len(parts) == 2:
                                try:
                                    min_size = int(parts[0])
                                    max_size = int(parts[1]) if parts[1] != "+" else 100000
                                    size_conditions.append({
                                        "range": {
                                            "experience.company_employees_count": {
                                                "gte": min_size,
                                                "lte": max_size
                                            }
                                        }
                                    })
                                except ValueError:
                                    continue
                        elif str(size_range).endswith("+"):
                            try:
                                min_size = int(str(size_range).replace("+", ""))
                                size_conditions.append({
                                    "range": {
                                        "experience.company_employees_count": {
                                            "gte": min_size
                                        }
                                    }
                                })
                            except ValueError:
                                continue
                    
                    if size_conditions:
                        experience_filter.append({
                            "bool": {
                                "should": size_conditions,
                                "minimum_should_match": 1
                            }
                        })
            
            if icp.get('revenue_range'):
                revenue_ranges = icp['revenue_range'] if isinstance(icp['revenue_range'], list) else []
                if revenue_ranges:
                    revenue_conditions = []
                    for revenue_range in revenue_ranges:
                        if "-" in str(revenue_range):
                            parts = str(revenue_range).split("-")
                            if len(parts) == 2:
                                try:
                                    min_revenue = int(parts[0].replace("M", "")) * 1000000
                                    max_revenue = int(parts[1].replace("M", "")) * 1000000
                                    revenue_conditions.append({
                                        "range": {
                                            "experience.company_annual_revenue_source_5": {
                                                "gte": min_revenue,
                                                "lte": max_revenue
                                            }
                                        }
                                    })
                                except ValueError:
                                    continue
                    
                    if revenue_conditions:
                        experience_filter.append({
                            "bool": {
                                "should": revenue_conditions,
                                "minimum_should_match": 1
                            }
                        })
            
            if icp.get('funding_stages'):
                funding_stages = icp['funding_stages'] if isinstance(icp['funding_stages'], list) else []
                if funding_stages:
                    funding_conditions = []
                    for stage in funding_stages:
                        funding_conditions.extend([
                            {
                                "match": {
                                    "experience.company_funding_stage": stage
                                }
                            },
                            {
                                "query_string": {
                                    "query": stage,
                                    "default_field": "experience.company_categories_and_keywords"
                                }
                            }
                        ])
                    
                    if funding_conditions:
                        experience_filter.append({
                            "bool": {
                                "should": funding_conditions,
                                "minimum_should_match": 1
                            }
                        })
            
            if icp.get('location'):
                locations = icp['location'] if isinstance(icp['location'], list) else []
                if locations:
                    location_conditions = []
                    for location in locations:
                        location_conditions.extend([
                            {
                                "match": {
                                    "location_country": location
                                }
                            },
                            {
                                "match": {
                                    "experience.company_hq_country": location
                                }
                            }
                        ])
                    experience_filter.append({
                        "bool": {
                            "should": location_conditions,
                            "minimum_should_match": 1
                        }
                    })
        
        if personas and len(personas) > 0:
            persona = personas[0]
            
            if persona.get('title_keywords'):
                titles = persona['title_keywords'] if isinstance(persona['title_keywords'], list) else []
                if titles:
                    title_query = " OR ".join([f'"{title}"' for title in titles])
                    experience_filter.append({
                        "query_string": {
                            "query": title_query,
                            "default_field": "experience.position_title"
                        }
                    })
            
            if persona.get('seniority_levels'):
                seniority = persona['seniority_levels'] if isinstance(persona['seniority_levels'], list) else []
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
            
            if persona.get('buying_roles'):
                buying_roles = persona['buying_roles'] if isinstance(persona['buying_roles'], list) else []
                if buying_roles:
                    role_conditions = []
                    for role in buying_roles:
                        role_conditions.append({
                            "match": {
                                "experience.position_title": role
                            }
                        })
                    experience_filter.append({
                        "bool": {
                            "should": role_conditions,
                            "minimum_should_match": 1
                        }
                    })
        
        if company_description and company_description.get('exclusion_criteria'):
            exclusion_criteria = company_description['exclusion_criteria'] if isinstance(company_description['exclusion_criteria'], list) else []
            if exclusion_criteria:
                exclusion_conditions = []
                for criteria in exclusion_criteria:
                    exclusion_conditions.append({
                        "bool": {
                            "must_not": [
                                {
                                    "query_string": {
                                        "query": criteria,
                                        "default_field": "experience.company_industry"
                                    }
                                }
                            ]
                        }
                    })
                query["query"]["bool"]["filter"].extend(exclusion_conditions)
        
        return query
    
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
                'funding_stage': active_experience.get('company_funding_stage', ''),
                'funding_amount': active_experience.get('company_funding_amount', ''),
                'funding_date': active_experience.get('company_funding_date', ''),
                'technology_stack': prospect_data.get('inferred_skills', []),
                'location_country': prospect_data.get('location_country', ''),
                'location_region': active_experience.get('company_hq_country', ''),
                'skills': prospect_data.get('inferred_skills', []),
                'experience': [exp.get('position_title', '') for exp in prospect_data.get('experience', [])],
                'education': [edu.get('institution_name', '') for edu in prospect_data.get('education', [])]
            }
        }
        
        return transformed_prospect

def main():
    # Section 1: Define the parameters
    print("Defining Parameters")
    
#    # company profiles

    company_profiles = [{ 
         'industries': ['Software'],
         'location': ['United States', 'Canada', 'United Kingdom']
     }]
#    company_profiles = [{
#        'industries': ['Technology', 'Software', 'SaaS'],
#        'employee_size_range': ['10-50', '51-200', '201-500'],
#        'revenue_range': ['1M-10M', '10M-50M', '50M-100M'],
#        'funding_stages': ['Series A', 'Series B', 'Series C', 'Seed'],
#        'location': ['United States', 'Canada', 'United Kingdom']
#    }]
    
    # personas
    personas = [{
        'title_keywords': ['CTO'],
    }]
#    personas = [{
#        'title_keywords': ['CEO', 'CTO', 'VP Engineering', 'Head of Engineering'],
#        'seniority_levels': ['C-Level', 'VP', 'Director'],
#        'buying_roles': ['Decision Maker', 'Influencer']
#    }]
    
    # company description and exclusion criteria
    company_description = {
        'description': 'Technology companies'
    }
#    company_description = {
#        'description': 'Technology companies with engineering teams',
#        'exclusion_criteria': ['Non-profit', 'Government']
#    }
    
    # search limit
    limit = 100

    # Section 2: Initialize the CoreSignal service
    print("Initializing Service")
    try:
        coresignal_service = CoreSignalService()
        print("Service initialized")
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure to set CORESIGNAL_API_KEY environment variable")
        return
    
    # Section 3: Build the Elasticsearch DSL query
    print("Building Search Query")
    try:
        query = coresignal_service.build_search_query(company_profiles=company_profiles, personas=personas, company_description=company_description)
        print("Query built successfully")
        print(f"Query preview: {json.dumps(query, indent=2)[:300]}...")
    except Exception as e:
        print(f"Error building query: {e}")
        return
    print()
    
    # Section 4: Call the API and get results
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
        
        # Display results
        print("\nResults")
        for i, prospect in enumerate(prospects, 1):
            print(f"\nProspect {i}:")
            print(f"  Name: {prospect.get('first_name', '')} {prospect.get('last_name', '')}")
            print(f"  Title: {prospect.get('job_title', '')}")
            print(f"  Company: {prospect.get('company_name', '')}")
            print(f"  Email: {prospect.get('email', '')}")
            print(f"  LinkedIn: {prospect.get('linkedin_url', '')}")
        
        # Save to JSON file
        with open("coresignal_results.json", 'w') as f:
            json.dump(prospects, f, indent=2)
        print(f"\nResults saved to: coresignal_results.json")
        
    except Exception as e:
        print(f"Error calling API: {e}")
        return
    
    print("\nExample completed")

if __name__ == "__main__":
    main()


