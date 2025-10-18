from typing import List, Dict, Any

class CoreSignalService:
    def __init__(self):
        self.api_key = 'oxBN1X7gc2ThK3jNSSHCON0oILDZ4wp5'
        self.base_url = "https://api.coresignal.com"
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _is_city(self, location: str) -> bool:
        """
        Determine if a location is a city (contains comma) or a country
        """
        return ',' in location or 'Metro Area' in location
    
    def _expand_industry_keywords(self, industry: str) -> str:
        """
        Expand industry terms with common variations
        """
        expansions = {
            'Cybersecurity': '"cybersecurity" OR "cyber security"',
            'Information Technology & Services': '"Information Technology & Services" OR "IT Services" OR "Information Technology"'
        }
        return expansions.get(industry, f'"{industry}"')
    
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
        
        # Handle position titles - FIXED: Always add to nested query
        if persona.get('position_title'):
            titles = persona['position_title'] if isinstance(persona['position_title'], list) else []
            if titles:
                if len(titles) == 1:
                    nested_must.append({
                        "match_phrase": {
                            "experience.position_title": titles[0]
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
        
        # Handle seniority levels
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
        
        # Handle company description
        if company_description and company_description.get('description'):
            description = company_description['description']
            nested_must.append({
                "query_string": {
                    "query": description,
                    "default_field": "experience.company_categories_and_keywords",
                    "default_operator": "AND"
                }
            })
        
        # Handle industries
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
        
        # Handle locations - Using location_full and experience.location fields
        if icp.get('location'):
            locations = icp['location'] if isinstance(icp['location'], list) else []
            if locations:
                # Build location queries with exact matching for ALL locations
                location_should = []
                
                for location in locations:
                    # Search in location_full field (outside nested experience)
                    location_should.append({
                        "match_phrase": {
                            "location_full": location
                        }
                    })
                    location_should.append({
                        "term": {
                            "location_full.exact": location
                        }
                    })
                    
                    # Search in experience.location field (inside nested experience)
                    location_should.append({
                        "match_phrase": {
                            "experience.location": location
                        }
                    })
                    location_should.append({
                        "term": {
                            "experience.location.exact": location
                        }
                    })
                
                # Only add if we have location queries - This creates the OR logic for ALL locations
                if location_should:
                    nested_must.append({
                        "bool": {
                            "should": location_should,
                            "minimum_should_match": 1  # Must match at least 1 location (OR logic)
                        }
                    })
        
        # Handle employee size range
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

        # Handle revenue range
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


# Example usage:
if __name__ == "__main__":
    service = CoreSignalService()
    
    # Your test data
    company_description = {
        'description': ''
    }

    company_profiles = [{
        'industries': [
            'Computer Software',
            'Information Technology & Services',
            'Computer Software',
            'Artificial Intelligence',
            'Cybersecurity'
        ],
        'location': [
            'Washington D.C. Metro Area',
            'Seattle, Washington, United States',
            'Washington, United States',
            'Bothell, Washington, United States',
            'North Bend, Washington, United States',
            'Bellingham, Washington, United States',
            'Burlington, Washington, United States',
            'Tacoma, Washington, United States'            
        ]        
    }]

    personas = [{
        'position_title': ['Software Engineer']
    }]
    
    # Generate the query
    query = service.build_search_query(company_profiles, personas, company_description)
    
    print("CoreSignal Search Query:")
    import json
    print(json.dumps(query, indent=2))

