# Score API Client Module

Simple Python client for the Funnel Alchemy Scoring API.

## Installation

```bash
pip install requests
```

## Quick Start

```python
import score_api_score as sc
import json

# Load data from query_example.json
with open('query_example.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Set data
scoring_settings = data['scoring_settings']
prospects = data['prospects']

# Call function
result = sc.scoring_function(scoring_settings, prospects)

# Print result
print(result)
```

## Usage

### Basic Example

```python
import score_api_score as sc

# Load data from query_example.json
with open('query_example.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Set data
scoring_settings = data['scoring_settings']
prospects = data['prospects']

# Call function
result = sc.scoring_function(scoring_settings, prospects)

# Print result
print(result)
```

### Manual Example

```python
import score_api_score as sc

# Complete scoring_settings
scoring_settings = {
    "company_description": "We are a B2B SaaS company specializing in sales automation and CRM solutions for mid-market and enterprise companies.",
    "exclusion_criteria": "We don't sell to companies with less than 50 employees, companies in the healthcare industry, or companies that are not B2B focused.",
    "industries": ["Technology", "Financial Services", "Manufacturing", "Professional Services"],
    "employee_range": ["51-200", "201-500", "501-1000", "1001-5000"],
    "revenue_range": ["$10M-$50M", "$50M-$100M", "$100M-$500M", "$500M-$1B"],
    "funding_stages": ["Series A", "Series B", "Series C", "Series D"],
    "title_keywords": ["Sales Director", "VP of Sales", "Chief Revenue Officer", "Sales Manager"],
    "seniority_levels": ["Senior Management", "Executive", "Middle Management"],
    "buying_roles": ["Decision Maker", "Influencer", "Budget Holder"],
    "locations": ["United States", "Canada"],
    "other_preferences": "Prefer technical founders and candidates with strong B2B SaaS experience"
}

# Complete prospect with flat structure
prospects = [
    {
        # Basic info
        "prospect_id": "12346",
        "full_name": "Sarah Johnson",
        
        # Profile info
        "headline": "VP of Sales at TechFlow Solutions",
        "summary": "Strategic sales leader with 12+ years experience in B2B SaaS",
        "location_country": "United States",
        "location_full": "San Francisco, California, United States",
        "inferred_skills": ["Sales Strategy", "Revenue Operations", "B2B SaaS"],
        "connections_count": 1200,
        "followers_count": 1800,
        
        # Current job
        "is_working": True,
        "active_experience_title": "VP of Sales",
        "active_experience_description": "Leading sales organization of 50+ reps",
        "active_experience_department": "Sales",
        "active_experience_management_level": "Executive",
        "is_decision_maker": True,
        
        # Current company
        "position_title": "VP of Sales",
        "department": "Sales",
        "management_level": "Executive",
        "duration_months": 18,
        "location": "San Francisco, CA",
        "company_id": "comp_790",
        "company_name": "TechFlow Solutions",
        "company_industry": "Technology",
        "company_followers_count": 25000,
        "company_size_range": "501-1000",
        "company_employees_count": 750,
        "company_categories_and_keywords": ["SaaS", "Sales Automation", "CRM", "B2B"],
        "company_hq_country": "United States",
        "company_last_funding_round_date": "2023-12-01",
        "company_last_funding_round_amount_raised": 75000000,
        "company_employees_count_change_yearly_percentage": 60,
        "company_hq_full_address": "456 Innovation Drive, San Francisco, CA 94105",
        "company_is_b2b": True,
        
        # Experience
        "total_experience_duration_months": 144,
        "total_experience_duration_months_breakdown_department": [
            {"department": "Sales", "total_experience_duration_months": 120},
            {"department": "Marketing", "total_experience_duration_months": 18},
            {"department": "Business Development", "total_experience_duration_months": 6}
        ],
        "total_experience_duration_months_breakdown_management_level": [
            {"management_level": "Executive", "total_experience_duration_months": 24},
            {"management_level": "Senior Management", "total_experience_duration_months": 48},
            {"management_level": "Middle Management", "total_experience_duration_months": 48},
            {"management_level": "Individual Contributor", "total_experience_duration_months": 24}
        ],
        
        # Education
        "education_degrees": [
            "Master's degree, Structural Engineering and Engineering Mechanics",
            "Mathematics",
            "Bachelor's degree, Civil & Environmental Engineering"
        ],
        
        # Languages (nested structure)
        "languages": [
            {
                "language": "English",
                "proficiency": "Native"
            },
            {
                "language": "French",
                "proficiency": "Fluent"
            }
        ],
        
        # Additional info
        "awards": ["Sales Leader of the Year 2023"],
        "certifications": ["Salesforce Certified Sales Cloud Consultant"],
        "courses": ["Executive Sales Leadership"],
        
        # Contact info
        "primary_professional_email": "sarah.johnson@techflow.com",
        "linkedin_url": "https://linkedin.com/in/sarahjohnson-techflow"
    }
]

# Call function
result = sc.scoring_function(scoring_settings, prospects)
print(result)
```

### Custom API Settings

```python
import score_api_score as sc

# Use custom API server and key
result = sc.scoring_function(
    scoring_settings=scoring_settings,
    prospects=prospects,
    base_url="https://your-api-server.com",
    api_key="your-api-key"
)
```

## Function Parameters

### `scoring_function(scoring_settings, prospects, base_url, api_key)`

**Parameters:**
- `scoring_settings` (dict): Scoring criteria and company description
- `prospects` (list): List of prospect objects to score
- `base_url` (str, optional): API server URL (default: "http://localhost:8000")
- `api_key` (str, optional): API authentication key (default: "test-key-123")

**Default Values:**
- `base_url="http://localhost:8000"` - Local API server
- `api_key="test-key-123"` - Test API key for development

**Returns:**
- `list`: Array of scoring results with scores and justifications

**Example Response:**
```json
[
    {
        "prospect_id": "12346",
        "score": 85,
        "justification": "Excellent fit: VP of Sales at technology company with 500+ employees, decision maker"
    }
]
```

## Prerequisites

1. **API Server Running**: Make sure the scoring API server is running:
   ```bash
   python main.py
   # or
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Required Files**:
   - `score_api_score.py` - Client module
   - `query_example.json` - Sample data (optional)

## Files

- `score_api_score.py` - Main client module
- `sample.py` - Example usage with query_example.json
- `query_example.json` - Sample data file

## Error Handling

The client handles common errors gracefully:

- **Connection errors**: Returns empty list and prints error message
- **API errors**: Returns empty list and prints error message
- **Timeout errors**: Returns empty list and prints error message

## Example with Error Handling

```python
import score_api_score as sc
import json

try:
    with open('query_example.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    result = sc.scoring_function(data['scoring_settings'], data['prospects'])
    
    if result:
        print(f"Scored {len(result)} prospects")
        for item in result:
            print(f"ID: {item['prospect_id']}, Score: {item['score']}")
    else:
        print("No results returned - check API server")
        
except FileNotFoundError:
    print("query_example.json not found")
except Exception as e:
    print(f"Error: {e}")
```
