# Prospect Scoring API Module

Python module for scoring prospects using OpenAI GPT models based on configurable Ideal Customer Profile (ICP) criteria.

## Features

- **Batch Processing**: Process up to 20 prospects per request
- **Flexible Scoring**: Configurable scoring criteria through scoring_settings
- **Error Handling**: Improved retry logic with exponential backoff for rate limits and API errors
- **Rate Limiting**: 60 requests per minute per API key
- **Simple API**: Easy-to-use interface
- **Type Safety**: Full type support with Pydantic

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenAI API key

### Installation Steps

1. **Copy the module folder** to your project directory
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set environment variables**:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

### Alternative: Install as Package

```bash
git clone <repository-url>
cd scoring_module
pip install -e .
```

## Quick Start

### 1. Set Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### 2. Basic Usage

```python
from scoring_module import score_prospects

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

# Scoring
results = score_prospects(scoring_settings, prospects)

# Results
for result in results:
    print(f"ID: {result.prospect_id}")
    print(f"Score: {result.score}")
    print(f"Justification: {result.justification}")

# Example output:
# [
#   {
#     "prospect_id": "12346",
#     "score": 96,
#     "justification": "Sarah is a VP of Sales at a B2B technology company with 750 employees and $50M+ revenue, aligning perfectly with our ICP. Her extensive experience in B2B SaaS and recent funding round of $75M indicate strong growth potential, justifying an excellent fit (A)."
#   }
# ]
```

### 3. Using Scorer Class

```python
from scoring_module import Scorer

# Create scorer with custom settings
scorer = Scorer(
    model="gpt-4o-mini",
    chunk_size=10,
    rate_limit_per_minute=30
)

# Scoring
results = scorer.score_prospects(scoring_settings, prospects)

# Score single prospect
result = scorer.score_single_prospect(scoring_settings, prospects[0])

# Check service health
health_status = scorer.get_health_status()
readiness_status = scorer.get_readiness_status()
```

## CLI Interface

### Install CLI

After installing the module, the `funnel-scorer` command is available:

```bash
# Score from JSON file
funnel-scorer score -i input.json -o results.json

# Score with settings from command line
funnel-scorer score -s '{"industries": ["Technology"]}' -p '[{"prospect_id": "1", "company_industry": "Technology"}]'

# Check service health
funnel-scorer health

# Check readiness
funnel-scorer ready
```

### Input JSON File Format

```json
{
  "scoring_settings": {
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
  },
  "prospects": [
{
  "prospect_id": "12346",
  "full_name": "Sarah Johnson",
      "headline": "VP of Sales at TechFlow Solutions",
      "summary": "Strategic sales leader with 12+ years experience in B2B SaaS",
      "location_country": "United States",
  "active_experience_title": "VP of Sales",
  "company_industry": "Technology",
  "company_size_range": "501-1000",
      "is_decision_maker": true,
      "company_is_b2b": true
    }
  ]
}
```

## API Documentation

### Main Classes

#### `Scorer`

Main class for scoring prospects.

```python
scorer = Scorer(
    api_key="your-api-key",  # Optional, can use environment variable
    model="gpt-4o-mini",     # OpenAI model
    chunk_size=20,           # Batch size
    rate_limit_per_minute=60, # Rate limit per minute
    max_concurrent_requests=10, # Maximum concurrent requests
    **openai_kwargs          # Additional parameters for OpenAI
)
```

**Methods:**

- `score_prospects(scoring_settings, prospects, api_key="default")` - Score list of prospects
- `score_single_prospect(scoring_settings, prospect, api_key="default")` - Score single prospect
- `get_health_status()` - Get service health status
- `get_readiness_status()` - Check service readiness

#### `ScoringSettings`

Pydantic model for scoring settings.

```python
from scoring_module import ScoringSettings

settings = ScoringSettings(
    company_description="We are a B2B SaaS company specializing in sales automation",
    industries=["Technology", "Financial Services"],
    employee_range=["51-200", "201-500"],
    title_keywords=["Sales Director", "VP of Sales"],
    seniority_levels=["Senior Management", "Executive"],
    buying_roles=["Decision Maker", "Influencer"]
)
```

#### `ScoringResult`

Scoring result.

```python
result = ScoringResult(
    prospect_id="12346",
    score=96,
    justification="Sarah is a VP of Sales at a B2B technology company with 750 employees and $50M+ revenue, aligning perfectly with our ICP. Her extensive experience in B2B SaaS and recent funding round of $75M indicate strong growth potential, justifying an excellent fit (A)."
)
```

### Exceptions

```python
from scoring_module import ScorerError, RateLimitError, APIError, TimeoutError

try:
    results = scorer.score_prospects(settings, prospects)
except RateLimitError:
    print("Rate limit exceeded")
except APIError:
    print("API error")
except ScorerError:
    print("General scoring error")
```

## Usage Examples

### Example 1: Basic Scoring

```python
from scoring_module import score_prospects

scoring_settings = {
    "company_description": "We are a B2B SaaS company specializing in sales automation",
    "industries": ["Technology", "Financial Services"],
    "employee_range": ["51-200", "201-500"],
    "title_keywords": ["Sales Manager", "VP of Sales"],
    "seniority_levels": ["Senior Management", "Executive"],
    "buying_roles": ["Decision Maker", "Influencer"]
}

prospects = [
    {
        "prospect_id": "1",
        "full_name": "John Smith",
        "company_industry": "Technology",
        "company_size_range": "51-200",
        "active_experience_title": "Sales Manager",
        "is_decision_maker": True,
        "company_is_b2b": True
    }
]

results = score_prospects(scoring_settings, prospects)
```

### Example 2: Advanced Configuration

```python
from scoring_module import Scorer
from scoring_module import ScoringSettings

# Create settings using Pydantic model
settings = ScoringSettings(
    company_description="AI startup for marketing automation",
    industries=["Technology", "E-commerce"],
    employee_range=["11-50", "51-200"],
    funding_stages=["Seed", "Series A"],
    title_keywords=["Marketing Manager", "CMO"],
    seniority_levels=["Middle Management", "Executive"],
    buying_roles=["Decision Maker", "Influencer"],
    locations=["United States", "Canada"],
    other_preferences="Prefer companies with active digital marketing"
)

# Create scorer with custom settings
scorer = Scorer(
    model="gpt-4o-mini",
    chunk_size=15,
    rate_limit_per_minute=30
)

results = scorer.score_prospects(settings, prospects)
```

### Example 3: Processing Large Batches

```python
# Create large list of prospects
prospects = []
for i in range(100):
    prospects.append({
        "prospect_id": f"prospect_{i}",
        "full_name": f"Prospect {i}",
        "company_industry": "Technology",
        "company_size_range": "51-200",
        "active_experience_title": "Sales Manager",
        "is_decision_maker": i % 2 == 0,
        "company_is_b2b": True
    })

# Process with batches of 20
scorer = Scorer(chunk_size=20)
results = scorer.score_prospects(scoring_settings, prospects)

# Analyze results
high_scores = [r for r in results if r.score >= 70]
print(f"High scores: {len(high_scores)}")
```

## Scoring Settings

### Required Fields

- `industries`: List of target industries for ICP
- `employee_range`: Employee count ranges
- `title_keywords`: Job title keywords
- `seniority_levels`: Seniority levels
- `buying_roles`: Buying process roles

### Optional Fields

- `company_description`: Description of your company
- `exclusion_criteria`: Exclusion criteria
- `revenue_range`: Revenue ranges
- `funding_stages`: Funding stages
- `locations`: Geographic locations
- `other_preferences`: Additional preferences

## Prospect Data Format

### Required Fields

- `prospect_id`: Unique identifier
- `company_industry`: Company industry
- `company_size_range`: Company size
- `active_experience_title`: Current job title

### Recommended Fields

- `is_decision_maker`: Whether they make buying decisions
- `active_experience_management_level`: Management level
- `company_is_b2b`: B2B or B2C company
- `total_experience_duration_months`: Total work experience
- `certifications`: Certifications
- `awards`: Awards

## Scoring Logic

### Evaluation Criteria

1. **Company Fit**: Industry, size, revenue, type (B2B/B2C)
2. **Persona Fit**: Job title, seniority level, authority
3. **Timing/Triggers**: Funding, growth, recent changes
4. **Geographic Rules**: Location match, exclusions
5. **Experience Factors**: Time at company, total experience, background

### Scoring Scale

- **A (85–100)**: Excellent fit — strong alignment with ICP, multiple matching signals
- **B (70–84)**: Good fit — solid match with few missing signals
- **C (31–69)**: Partial or unclear fit — some match, but weak/uncertain
- **D (0–30)**: Poor fit — clear mismatch or explicit disqualification

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: OpenAI model (default: gpt-4o-mini)
- `OPENAI_MAX_RETRIES`: Maximum retry count (default: 2)
- `OPENAI_REQUEST_TIMEOUT_S`: Request timeout in seconds (default: 30)
- `OPENAI_TEMPERATURE`: Generation temperature (default: 0)

## Development

### Development Installation

```bash
git clone <repository-url>
cd scoring_module
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black .
flake8 .
mypy .
```

## License

MIT License

## Support

For technical support, contact the development team or create an issue in the repository.