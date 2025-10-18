import os
import sys
import asyncio
import json
import requests
import random
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2 import Error
from datetime import datetime


from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path(__file__).parent / '.env'

for i in range(3):
    if dotenv_path.exists():
        print(f"Found .env file !")
        break
    else:
        print(f"WARNING: .env file does not exist at {dotenv_path}, trying parent directory...")
        dotenv_path = dotenv_path.parent.parent / '.env'
if not dotenv_path.exists():
    raise FileNotFoundError(f"Could not find .env file in the directory tree starting from {Path(__file__).parent}")


load_dotenv(dotenv_path)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PWD = os.getenv("POSTGRES_PWD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
db_url = f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PWD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'







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
            #with open('test_data.json', 'w') as file:
            #    json.dump(data, file, indent=4)


            prospect_ids = data if isinstance(data, list) else []
            print(f"Found {len(prospect_ids)} prospect IDs from CoreSignal API")
            
            if len(prospect_ids) > limit:
                selected_prospect_ids = random.sample(prospect_ids, limit)
            else:
                selected_prospect_ids = prospect_ids
            
            transformed_prospects = []
            prospects_list = []
            for prospect_id in selected_prospect_ids:
                try:
                    prospect_data = await self.get_prospect_details(prospect_id)
                    prospects_list.append(prospect_data)
                    print(f"TTTTTTTTTTTTTT type of prospect data is |{type(prospect_data)}|")
                    with open('test_data2.json', 'a') as file:
                        json.dump(prospect_data, file, indent=4)
                #    if prospect_data:
                #        transformed_prospect = self.transform_prospect_data(prospect_data)
                #        transformed_prospects.append(transformed_prospect)
                except Exception as e:
                    print(f"Failed to get details for prospect {prospect_id}: {str(e)}")
                    continue
            
            print(f"Successfully transformed {len(transformed_prospects)} prospects from CoreSignal")
            # return both the list of ids lcoate din "data" and the full json
            # located in prospect_data
            #return transformed_prospects
            return data, prospects_list
            
        except Exception as e:
            print(f"Error searching CoreSignal prospects: {str(e)}")
            raise Exception(f"Failed to search CoreSignal prospects: {str(e)}")
    
    async def get_prospect_details(self, prospect_id: int) -> Optional[Dict]:
        """
        This function will take a prospect id in input and get the full details 
        of that prospect from coresignal
        """
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


def get_full_prospects_list(vendorname):
    """
    Retrieves a list of all vendorid values from the prospects table for a specific vendor.

    Args:
        vendorname (str): The name of the vendor to filter by.

    Returns:
        list: A list of all vendorid values (as strings) from the prospects table for the given vendor.
    """
    try:
        # Use the database connection details from the provided script
        connection = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PWD,
            database=POSTGRES_DB
        )
        
        # Create a cursor to execute the query
        cursor = connection.cursor()
        
        # Query to select all vendorid values from the prospects table for the given vendorname
        cursor.execute("SELECT vendorid FROM prospects WHERE vendorname = %s", (vendorname,))
        
        # Fetch all results and extract vendorids into a list
        prospect_vendorids = [row[0] for row in cursor.fetchall()]
        
        return prospect_vendorids
    
    except Error as e:
        print(f"Error connecting to PostgreSQL or executing query: {e}")
        return []
    
    finally:
        # Close cursor and connection if they were created
        if cursor:
            cursor.close()
        if connection:
            connection.close()



def insert_or_update_prospects(vendorname, prospects_list, existing_ids):
    """
    Inserts or updates prospect records in the prospects table based on vendorid.

    Args:
        vendorname (str): Name of the vendor providing the data.
        prospects_list (list): List of dictionaries, each representing a prospect.
        existing_ids (list): List of vendorid values already in the prospects table.

    Returns:
        dict: Summary of operations performed, e.g., {'inserted': count, 'updated': count, 'errors': count}.
    """
    summary = {'inserted': 0, 'updated': 0, 'errors': 0}
    
    try:
        # Connect to the database
        connection = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PWD,
            database=POSTGRES_DB
        )
        cursor = connection.cursor()

        for prospect_data in prospects_list:
            try:
                # Use the dictionary directly (no json.loads needed)
                vendorid = str(prospect_data.get('id'))  # Assuming 'id' in dict maps to vendorid
                full_name = prospect_data.get('full_name')
                first_name = prospect_data.get('first_name')
                last_name = prospect_data.get('last_name')
                linkedin_url = prospect_data.get('linkedin_url')
                is_deleted = prospect_data.get('is_deleted')
                
                # Handle date fields with proper parsing
                def parse_timestamp(timestamp_str):
                    if timestamp_str:
                        try:
                            return datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                        except ValueError:
                            return None
                    return None
                
                created_at = parse_timestamp(prospect_data.get('created_at'))
                updated_at = parse_timestamp(prospect_data.get('updated_at'))
                checked_at = parse_timestamp(prospect_data.get('checked_at'))
                changed_at = parse_timestamp(prospect_data.get('changed_at'))
                
                # Phone number and email (not in Coresignal example, so set to None if missing)
                phone_number = prospect_data.get('phone_number')
                email_address = prospect_data.get('primary_professional_email')

                # Convert the dictionary to a JSON string for vendordata
                vendordata = json.dumps(prospect_data)

                # Common fields for both insert and update
                params = (
                    vendorname,
                    vendorid,
                    is_deleted,
                    created_at,
                    updated_at,
                    checked_at,
                    changed_at,
                    linkedin_url,
                    full_name,
                    first_name,
                    last_name,
                    phone_number,
                    email_address,
                    vendordata,
                    updated_at,  # Map updated_at to vendor_last_updated
                    'active'     # Default status
                )

                if vendorid in existing_ids:
                    # Update existing record
                    query = """
                        UPDATE prospects
                        SET is_deleted = %s,
                            created_at = %s,
                            updated_at = %s,
                            checked_at = %s,
                            changed_at = %s,
                            linkedin_url = %s,
                            full_name = %s,
                            first_name = %s,
                            last_name = %s,
                            phone_number = %s,
                            email_address = %s,
                            vendordata = %s,
                            vendor_last_updated = %s,
                            status = %s
                        WHERE vendorname = %s AND vendorid = %s
                    """
                    cursor.execute(query, params + (vendorname, vendorid))
                    summary['updated'] += 1
                else:
                    # Insert new record
                    query = """
                        INSERT INTO prospects (
                            vendorname, vendorid, is_deleted, created_at, updated_at,
                            checked_at, changed_at, linkedin_url, full_name, first_name,
                            last_name, phone_number, email_address, vendordata,
                            vendor_last_updated, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, params)
                    summary['inserted'] += 1

            except Exception as e:
                print(f"Error processing prospect data: {e}")
                summary['errors'] += 1
                continue

        # Commit the transaction
        connection.commit()
        return summary

    except Error as e:
        print(f"Database error: {e}")
        summary['errors'] += len(prospects_list)
        return summary

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()







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
    #limit = 10
    #limit = 50
    limit = 5

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
        
        idlist, prospects_json_list = asyncio.run(search_prospects())
        
        print(f"API call successful!")
        #print(f"Found {len(prospects)} prospects")
        print(f"TYPE of P json list is |{type(prospects_json_list)}| ")
        print(f"Found |{len(prospects_json_list)}| in prospects JSON LIST")
        

        #get the full list of existing prospects
        print(f"beore call to INSERT")
        existing_prospects_list = get_full_prospects_list("coresignal")
        print(f"after call to INSERT")


        insert_or_update_prospects("coresignal", prospects_json_list, existing_prospects_list)


        ## Display results
        print("\nResults")
        for i, prospect in enumerate(prospects_json_list, 1):
            print(f"\nProspect {i}:")
            print(f"  Name: {prospect.get('first_name', '')} {prospect.get('last_name', '')}")
            print(f"  Title: {prospect.get('job_title', '')}")
            print(f"  Company: {prospect.get('company_name', '')}")
            print(f"  Email: {prospect.get('email', '')}")
            print(f"  LinkedIn: {prospect.get('linkedin_url', '')}")
        
        ## Save to JSON file
        #with open("coresignal_results.json", 'w') as f:
        #    json.dump(prospects, f, indent=2)
        #print(f"\nResults saved to: coresignal_results.json")
        
    except Exception as e:
        print(f"Error calling API: {e}")
        return
    
    print("\nExample completed")


def main2():
    #test the get list from database 
    id_list = get_full_prospects_list("coresignal")
    print(f"size of id_list = |{len(id_list)}|")    

if __name__ == "__main__":
    main()
    #main2()


