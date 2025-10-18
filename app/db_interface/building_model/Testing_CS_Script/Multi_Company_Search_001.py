import os
import sys
import asyncio
import json
import requests
import random
from typing import List, Dict, Any, Optional

from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables (adapted from your code)
dotenv_path = Path(__file__).parent / '.env'
for i in range(3):
    if dotenv_path.exists():
        print(f"Found .env file!")
        break
    else:
        print(f"WARNING: .env file does not exist at {dotenv_path}, trying parent directory...")
        dotenv_path = dotenv_path.parent.parent / '.env'
if not dotenv_path.exists():
    raise FileNotFoundError(f"Could not find .env file in the directory tree starting from {Path(__file__).parent}")

load_dotenv(dotenv_path)

# CoreSignalService class (extended from your employee example to include company search)
class CoreSignalService:
    def __init__(self):
        self.api_key = os.getenv('CORESIGNAL_API_KEY', 'U3UG17rFdQ0jv47caYoTIjwyKnnmtAtH')  # Use env var or fallback to your hardcoded key
        self.base_url = "https://api.coresignal.com"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    def build_company_search_query(self, company_profiles: List[Dict]) -> Dict[str, Any]:
            """
            Builds an ES DSL query for the Multi-source Company API, focusing on key_executive_arrivals.
            Supports other fields (industries, location, etc.) if provided.
            """
            icp = company_profiles[0] if company_profiles and len(company_profiles) > 0 else {}
            query = {
                "query": {
                    "bool": {
                        "must": []
                    }
                }
            }
            must_clauses = query["query"]["bool"]["must"]

            # Handle key_executive_arrivals
            if icp.get('key_executive_arrivals'):
                kea_config = icp['key_executive_arrivals']
                # Basic existence filter
                if kea_config.get('exists', False):
                    must_clauses.append({
                        "exists": {"field": "key_executive_arrivals"}
                    })
                # Optional date range filter (assumes field has a date subfield)
                if kea_config.get('date_range'):
                    must_clauses.append({
                        "nested": {
                            "path": "key_executive_arrivals",
                            "query": {
                                "range": {
                                    "key_executive_arrivals.arrival_date": {
                                        "gte": kea_config['date_range']
                                    }
                                }
                            }
                        }
                    })
                # Optional role filter (e.g., C-level only)
                if kea_config.get('role'):
                    must_clauses.append({
                        "nested": {
                            "path": "key_executive_arrivals",
                            "query": {
                                "match": {
                                    "key_executive_arrivals.role": kea_config['role']
                                }
                            }
                        }
                    })



    def build_company_search_query(self, company_profiles: List[Dict]) -> Dict[str, Any]:
        """
        Builds an Elasticsearch DSL query for searching companies in the Multi-source Company API.
        
        This method constructs a query based on the provided company profiles. The query uses a 'bool' must clause
        to combine filters for industries, locations, employee size ranges, revenue ranges, and other criteria.
        
        Key assumptions about the company index schema (based on Coresignal documentation):
        - 'industry': The primary industry of the company (string).
        - 'location': The company's location (string, e.g., 'United States' or 'New York, NY').
        - 'employees_count': Number of employees (integer).
        - 'annual_revenue_source_1' or 'annual_revenue_source_5': Revenue fields from different sources (integer, in USD).
        - 'categories_and_keywords': A text field for company categories, keywords, or descriptions (string).
        - Other potential fields: 'name', 'founded_year', 'website', etc. (not used in this example).

        The query ensures active companies (if applicable) and applies filters logically:
        - Industries: Matched against 'industry' or 'categories_and_keywords' with expansions for common variations.
        - Locations: Phrase match on 'location'.
        - Employee size: Range filter on 'employees_count'.
        - Revenue: Range filter on revenue sources (OR logic across sources).
        - Technologies/Keywords: Multi-match on description or keyword fields.

        Args:
            company_profiles (List[Dict]): List of company profile dictionaries with keys like 'industries', 'location',
                                           'employee_size_range', 'revenue_range', 'technologies'.

        Returns:
            Dict[str, Any]: The Elasticsearch DSL query dictionary.
        """

        icp = company_profiles[0] if company_profiles and len(company_profiles) > 0 else {}
        query = {
            "query": {
                "bool": {
                    "must": []
                }
            }
        }
        must_clauses = query["query"]["bool"]["must"]

        # Handle key_executive_arrivals (nested array filter for arrival_date)
        if icp.get('key_executive_arrivals'):
            kea_config = icp['key_executive_arrivals']
            arrival_date = kea_config.get('arrival_date')
            if arrival_date:
                must_clauses.append({
                    "match": {
                        "key_executive_arrivals": arrival_date
                    }
#                    "nested": {
#                        "path": "key_executive_arrivals",
#                        "query": {
#                            "term": {  # Exact match for the arrival_date string
#                                "key_executive_arrivals": arrival_date
#                            }
#                        }
#                    }
                })
            else:
                # Fallback: If no specific date, filter for any non-empty arrivals (exists on the array)
                must_clauses.append({
                    "exists": {"field": "key_executive_arrivals"}
                })

            # Optional role filter (e.g., C-level only)
            if kea_config.get('role'):
                must_clauses.append({
                    "nested": {
                        "path": "key_executive_arrivals",
                        "query": {
                            "match": {
                                "key_executive_arrivals.role": kea_config['role']
                            }
                        }
                    }
                })


        # Handle locations (phrase match on location field)
        if icp.get('location'):
            locations = icp['location'] if isinstance(icp['location'], list) else [icp['location']]
            if locations:
                location_should = [{"match_phrase": {"location": loc}} for loc in locations]
                must_clauses.append({
                    "bool": {
                        "should": location_should,
                        "minimum_should_match": 1  # OR logic for multiple locations
                    }
                })

        # Handle technologies/keywords (multi-match on description or keyword fields)
        if icp.get('technologies'):
            technologies = icp['technologies'] if isinstance(icp['technologies'], list) else [icp['technologies']]
            if technologies:
                tech_should = [{
                    "multi_match": {
                        "query": tech,
                        "fields": ["description", "categories_and_keywords"],
                        "operator": "or"
                    }
                } for tech in technologies]
                must_clauses.append({
                    "bool": {
                        "should": tech_should,
                        "minimum_should_match": 1
                    }
                })

        # Employee size range
        if icp.get('employee_size_range'):
            size_ranges = icp['employee_size_range'] if isinstance(icp['employee_size_range'], list) else [icp['employee_size_range']]
            min_size = float('inf')
            max_size = 0
            for size_range in size_ranges:
                if "-" in str(size_range):
                    parts = str(size_range).split("-")
                    if len(parts) == 2:
                        try:
                            range_min = int(parts[0].strip())
                            range_max = int(parts[1].strip())
                            min_size = min(min_size, range_min)
                            max_size = max(max_size, range_max)
                        except ValueError:
                            print(f"Invalid size range format: {size_range}")
                            continue
                elif str(size_range).endswith("+"):
                    try:
                        min_size = min(min_size, int(str(size_range).replace("+", "").strip()))
                        max_size = float('inf')
                    except ValueError:
                        print(f"Invalid size range format: {size_range}")
                        continue
            if min_size != float('inf'):
                range_filter = {
                    "range": {
                        "employees_count": {
                            "gte": min_size
                        }
                    }
                }
                if max_size != float('inf'):
                    range_filter["range"]["employees_count"]["lte"] = max_size
                must_clauses.append(range_filter)

        # Revenue range (similar to employee, but on company fields)
        if icp.get('revenue_range'):
            revenue_ranges = icp['revenue_range'] if isinstance(icp['revenue_range'], list) else [icp['revenue_range']]
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
                                    "annual_revenue_source_1": {
                                        "gte": min_revenue
                                    }
                                }
                            },
                            {
                                "range": {
                                    "annual_revenue_source_5": {
                                        "gte": min_revenue
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                }
                if max_revenue != float('inf'):
                    range_filter["bool"]["should"][0]["range"]["annual_revenue_source_1"]["lte"] = max_revenue
                    range_filter["bool"]["should"][1]["range"]["annual_revenue_source_5"]["lte"] = max_revenue
                must_clauses.append(range_filter)

        return query

    async def search_companies(self, company_profiles: List[Dict], limit: int) -> List[Dict]:
        """
        Searches for companies using the built ES DSL query, fetches company IDs, and retrieves detailed data.

        This method:
        1. Builds the ES DSL query using build_company_search_query.
        2. POSTs to /v2/company_multi_source/search/es_dsl to get a list of company IDs.
        3. Randomly samples up to 'limit' IDs if more are returned.
        4. Fetches detailed company data for each ID using GET /v2/company_multi_source/collect/{company_id}.
        5. Returns the list of detailed company data dictionaries.

        Args:
            company_profiles (List[Dict]): Company profile filters (same as build_company_search_query).
            limit (int): Maximum number of companies to return.

        Returns:
            List[Dict]: List of detailed company data dictionaries.

        Raises:
            Exception: If API calls fail.
        """
        try:
            query = self.build_company_search_query(company_profiles)
            
            print(f"CoreSignal Company Search Query: {json.dumps(query, indent=2)}")
            print(f"CoreSignal Headers: {self.headers}")
            
            #f"{self.base_url}/v2/company_multi_source/search/es_dsl",
            response = requests.post(
                f"{self.base_url}/cdapi/v1/multi_source/company/search/es_dsl",
                headers=self.headers,
                json=query,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"CoreSignal API error: {response.status_code} - {response.text}")
                raise Exception(f"CoreSignal API returned {response.status_code}: {response.text}")
            
            data = response.json()
            company_ids = data if isinstance(data, list) else []
            print(f"Found {len(company_ids)} company IDs from CoreSignal API")
            
            if len(company_ids) > limit:
                selected_company_ids = random.sample(company_ids, limit)
            else:
                selected_company_ids = company_ids
            
            companies_list = []
            for company_id in selected_company_ids:
                try:
                    company_data = await self.get_company_details(company_id)
                    if company_data:
                        companies_list.append(company_data)
                        # Optionally save to file as in your code
                        with open('company_test_data.json', 'a') as file:
                            json.dump(company_data, file, indent=4)
                except Exception as e:
                    print(f"Failed to get details for company {company_id}: {str(e)}")
                    continue
            
            print(f"Successfully fetched {len(companies_list)} companies from CoreSignal")
            return companies_list
            
        except Exception as e:
            print(f"Error searching CoreSignal companies: {str(e)}")
            raise Exception(f"Failed to search CoreSignal companies: {str(e)}")

    async def get_company_details(self, company_id: int) -> Optional[Dict]:
        """
        Fetches detailed company data for a given company ID.

        Args:
            company_id (int): The ID of the company.

        Returns:
            Optional[Dict]: Company data dictionary or None if failed.
        """
        try:
            response = requests.get(
                f"{self.base_url}/v2/company_multi_source/collect/{company_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"CoreSignal company details error: {response.status_code} - {response.text}")
                return None
            return response.json()
            
        except Exception as e:
            print(f"Error getting company details for {company_id}: {str(e)}")
            return None

    # Reuse your _expand_industry_keywords method (unchanged)
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

# Example usage in main function
def main():
    # Define company profiles (adapted from your employee example, but for companies directly)
    #company_profiles = [{
    #    "key_executive_arrivals": {
    #        "exists": True,  # Require the field to exist (i.e., companies with any executive arrivals)
    #        "date_range": "2025-01-01"  # Optional: Filter for arrivals after this date
    #    }
    #}]

    company_profiles = [{
        "key_executive_arrivals": {
            "exists": True,  # Require the field to exist (i.e., companies with any executive arrivals)
            "arrival_date": "Apr 2025"  # The exact value to match
        }
    }]




    #limit = 100  # Adjust as needed
    limit = 5  # Adjust as needed

    # Initialize service
    print("Initializing Service")
    try:
        coresignal_service = CoreSignalService()
        print("Service initialized")
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure to set CORESIGNAL_API_KEY environment variable")
        return

    # Call the API and get results
    print("Calling CoreSignal Company API")
    try:
        async def search_companies_wrapper():
            return await coresignal_service.search_companies(
                company_profiles=company_profiles,
                limit=limit
            )
        
        companies_list = asyncio.run(search_companies_wrapper())
        
        print(f"API call successful!")
        print(f"Found {len(companies_list)} companies")
        
        # Optionally process or save the companies_list (similar to your prospects handling)
        # For example, print a preview
        for i, company in enumerate(companies_list, 1):
            print(f"\nCompany {i}:")
            print(f"  Name: {company.get('name', '')}")
            print(f"  Industry: {company.get('industry', '')}")
            print(f"  Location: {company.get('location', '')}")
            print(f"  Employees: {company.get('employees_count', 0)}")
            print(f"  Revenue: {company.get('annual_revenue_source_1', 0)}")
        
        # Save to JSON file
        with open("coresignal_company_results.json", 'w') as f:
            json.dump(companies_list, f, indent=2)
        print(f"\nResults saved to: coresignal_company_results.json")
        
    except Exception as e:
        print(f"Error calling API: {e}")
        return

    print("\nCompany search example completed")

if __name__ == "__main__":
    main()


