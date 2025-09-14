# Funnel Alchemy Scoring API

## Overview

Funnel Alchemy Scoring API is a service for evaluating potential customers (prospects) using OpenAI GPT models. The API accepts prospect data and returns a score from 0 to 100 with justification.

## Features

- **Batch Processing**: Process up to 20 prospects per request
- **Flexible Scoring**: Configurable evaluation criteria through scoring_settings
- **Error Handling**: Improved retry logic with exponential backoff for rate limits and API errors
- **Rate Limiting**: 60 requests per minute per API key
- **Authentication**: Bearer token authentication
- **Health Checks**: Endpoints for service monitoring

## Authentication

All requests require the `Authorization: Bearer <your-api-key>` header.

**Available API keys for testing:**
- `test-key-123`
- `beta-key-456`

## API Endpoints

### Health Checks

#### GET /health
Basic health check (no model call).

```bash
curl -X GET "http://localhost:8000/health"
```

#### GET /ready
Readiness check with light model test.

```bash
curl -X GET "http://localhost:8000/ready"
```

### Scoring Endpoints

#### POST /score-prospects-batch (Recommended)
Main endpoint for batch prospect scoring.

```bash
curl -X POST "http://localhost:8000/score-prospects-batch" \
  -H "Authorization: Bearer test-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "scoring_settings": {
      "company_description": "We are a B2B SaaS company specializing in sales automation and CRM solutions for mid-market and enterprise companies.",
      "exclusion_criteria": "We don't sell to companies with less than 50 employees, companies in the healthcare industry, or companies that are not B2B focused.",
      "industries": ["Technology", "Financial Services", "Manufacturing"],
      "employee_range": ["51-200", "201-500", "501-1000"],
      "revenue_range": ["$10M-$50M", "$50M-$100M", "$100M-$500M"],
      "title_keywords": ["Sales Director", "VP of Sales", "Chief Revenue Officer"],
      "seniority_levels": ["Senior Management", "Executive", "Middle Management"],
      "buying_roles": ["Decision Maker", "Influencer", "Budget Holder"],
      "locations": ["United States", "Canada"],
      "other_preferences": "Prefer prospects with technical backgrounds or experience in scaling sales teams"
    },
    "prospects": [
      {
        "prospect_id": "12346",
        "full_name": "Sarah Johnson",
        "basic_profile": {
          "headline": "VP of Sales at TechFlow Solutions",
          "location_country": "United States"
        },
        "current_job": {
          "active_experience_title": "VP of Sales",
          "active_experience_management_level": "Executive",
          "is_decision_maker": true
        },
        "current_company": {
          "company_industry": "Technology",
          "company_size_range": "501-1000",
          "company_is_b2b": true,
          "company_employees_count_change_yearly_percentage": 25.5,
          "company_last_funding_round_amount_raised": 5000000
        },
        "total_experience": {
          "total_experience_duration_months": 144,
          "department_specific_experience_months": {
            "Sales": 60,
            "Business Development": 24
          }
        },
        "certifications": ["Salesforce Admin", "Gong Certified"],
        "awards": ["Top Performer 2023", "Sales Excellence Award"]
      }
    ]
  }'
```

#### POST /score_prospects (Legacy)
Compatible endpoint for single scoring (redirects to batch logic).

```bash
curl -X POST "http://localhost:8000/score_prospects" \
  -H "Authorization: Bearer test-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "scoring_settings": {
      "industries": ["Technology"],
      "employee_range": ["51-200"],
      "title_keywords": ["Sales Director", "VP of Sales"],
      "other_preferences": "Prefer technical founders"
    },
    "prospects": [
      {
        "prospect_id": "single_prospect",
        "basic_profile": {
          "headline": "VP of Sales at Startup"
        },
        "current_company": {
          "company_industry": "Technology",
          "company_size_range": "51-200",
          "company_employees_count_change_yearly_percentage": 45.2,
          "company_last_funding_round_amount_raised": 2000000
        },
        "certifications": ["HubSpot Certified"],
        "awards": ["Rookie of the Year 2023"]
      }
    ]
  }'
```

## Request Format

### Scoring Settings
Object with configurable fields for evaluation criteria:

```json
{
  "company_description": "Description of your company and what you sell",
  "exclusion_criteria": "Criteria for disqualifying prospects",
  "industries": ["Technology", "Financial Services", "Manufacturing"],
  "employee_range": ["51-200", "201-500", "501-1000"],
  "revenue_range": ["$10M-$50M", "$50M-$100M", "$100M-$500M"],
  "funding_stages": ["Series A", "Series B", "Series C"],
  "title_keywords": ["Sales Director", "VP of Sales", "Chief Revenue Officer"],
  "seniority_levels": ["Senior Management", "Executive", "Middle Management"],
  "buying_roles": ["Decision Maker", "Influencer", "Budget Holder"],
  "locations": ["United States", "Canada"],
  "other_preferences": "Additional soft guidelines (e.g., 'prefer technical founders')"
}
```

### Prospect Format
Each prospect is a JSON object with the following structure:

```json
{
  "prospect_id": "12346",
  "full_name": "Sarah Johnson",
  "basic_profile": {
    "headline": "VP of Sales at TechFlow Solutions",
    "summary": "Strategic sales leader with 12+ years experience...",
    "location_country": "United States",
    "location_full": "San Francisco, California, United States"
  },
  "current_job": {
    "is_working": true,
    "active_experience_title": "VP of Sales",
    "active_experience_management_level": "Executive",
    "is_decision_maker": true
  },
  "current_company": {
    "company_industry": "Technology",
    "company_size_range": "501-1000",
    "company_is_b2b": true,
    "company_last_funding_round_amount_raised": "$75M"
  },
  "total_experience": {
    "total_experience_duration_months": 144
  }
}
```

## Response Format

### Success Response
API returns a simple array of scoring results:

```json
[
  {
    "prospect_id": "12346",
    "score": 97,
    "justification": "Sarah is a VP of Sales at a technology company with 750 employees and $50M+ revenue, aligning perfectly with our ICP. Her executive role and decision-making authority further enhance her fit, resulting in an excellent score (A)."
  },
  {
    "prospect_id": "12347",
    "score": 90,
    "justification": "Michael is a Sales Director at TechFlow Solutions, also in the technology sector with 750 employees. His senior management position and decision-making role indicate strong alignment with our ICP, leading to a high score (A)."
  },
  {
    "prospect_id": "12348",
    "score": 74,
    "justification": "Jennifer is a Senior Account Executive at a technology company with 750 employees, which fits our ICP. However, her role as a non-decision maker and slightly lower seniority results in a good but not excellent score (B)."
  }
]
```

### Error Response
```json
{
  "detail": "Rate limit exceeded"
}
```

## Response Headers

All responses include rich metadata in headers for monitoring and debugging:

- `X-Scorer-Version`: API version (e.g., "1.0.0")
- `X-Request-Id`: Unique request ID for tracing
- `X-Count`: Total number of prospects processed
- `X-Ok`: Number of successfully processed prospects
- `X-Ok-Share`: Success rate as decimal (0.0-1.0)
- `X-Retries-Total`: Total number of retry attempts
- `X-Latency-S`: Total processing time in seconds
- `X-Error-Counts`: JSON with error counts by category

### Example Headers
```
X-Scorer-Version: 1.0.0
X-Request-Id: 5151c1c5-2d7a-434e-bc80-9cdbe0bfd67c
X-Count: 3
X-Ok: 3
X-Ok-Share: 1.000
X-Retries-Total: 0
X-Latency-S: 5.093
X-Error-Counts: {}
```

## Error Categories

API returns standardized errors:

- `invalid_json`: Invalid JSON from model
- `api_timeout`: Model request timeout
- `api_ratelimit`: Provider rate limit exceeded
- `api_failure`: Provider API failure
- `invalid_prospect_payload`: Invalid prospect data format

## Rate Limits

- **60 requests per minute** per API key
- **Maximum 10 concurrent requests** to the service
- Returns HTTP 429 when limit exceeded

## Scoring Logic

### Evaluation Criteria
The model evaluates prospects based on:

1. **Company Fit**: Industry alignment, company size, revenue, maturity signals
2. **Persona Fit**: Job title, seniority level, decision-making authority
3. **Timing Triggers**: Funding stage, growth signals, recent changes
4. **Location Rules**: Country matching and exclusion criteria
5. **Experience Factors**: Time at company, total experience, background

### Scoring Bands
- **A (85–100)**: Excellent fit — strong alignment with ICP, multiple matching signals
- **B (70–84)**: Good fit — solid match with a few missing signals  
- **C (31–69)**: Partial or unclear fit — some match, but weak/uncertain
- **D (0–30)**: Poor fit — clear mismatch or explicit disqualification

### Key Factors
- **Industry match** with scoring_settings.industries
- **Company size** alignment with scoring_settings.employee_range
- **Job title** relevance to scoring_settings.title_keywords
- **Seniority level** matching scoring_settings.seniority_levels
- **Decision-making authority** (is_decision_maker field)
- **Location compliance** with scoring_settings.locations
- **B2B vs B2C** filtering (company_is_b2b field)
- **Management level** (active_experience_management_level)
- **Additional preferences** (other_preferences field for soft guidelines)
- **Exclusion criteria** violations result in disqualification

## Installation & Setup

1. **Clone repository**
```bash
git clone <repository-url>
cd app
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set environment variables**
```bash
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"  # optional, defaults to gpt-4o-mini
```

4. **Run the service**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4o-mini)
- `OPENAI_MAX_RETRIES`: Maximum retry attempts (default: 2)
- `OPENAI_REQUEST_TIMEOUT_S`: Request timeout in seconds (default: 30)

## Development

### Project Structure
```
app/
├── main.py              # FastAPI application and endpoints
├── models.py            # Pydantic data models
├── openai_client.py     # OpenAI API client
├── prompt.py            # Prompt generation
├── utils.py             # Utility functions
├── requirements.txt     # Python dependencies
└── README.md           # Documentation
```

### Testing
```bash
# Health check
curl http://localhost:8000/health

# Ready check
curl http://localhost:8000/ready

# Test scoring with valid API key
curl -X POST "http://localhost:8000/score-prospects-batch" \
  -H "Authorization: Bearer test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"scoring_settings":{},"prospects":[{"prospect_id":"test"}]}'
```

### Testing in Swagger UI

1. **Open Swagger UI**: Navigate to `http://localhost:8000/docs`
2. **Authorize**: Click the **🔒 Authorize** button in the top-right corner
3. **Enter API Key**: In the authorization modal, enter:
   ```
   Bearer test-key-123
   ```
4. **Click Authorize**: Close the modal
5. **Test Endpoints**: Now you can test all endpoints with automatic authorization

**Available test API keys:**
- `test-key-123`
- `beta-key-456`

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check API key in Authorization header
2. **429 Too Many Requests**: Rate limit exceeded, wait a minute
3. **503 Service Unavailable**: Service overloaded, try later
4. **Invalid JSON**: Check prospect data format

### Logs
Service logs all requests with detailed information:
- Request ID
- Prospect count
- Processing status
- Error categories
- Execution time
- Retry count

## Python Client Module

For easy integration, use the provided Python client module:

```python
import score_api_score as sc

# Simple usage
result = sc.scoring_function(scoring_settings, prospects)
```

See [CLIENT_README.md](CLIENT_README.md) for detailed client documentation and examples.

## Support

For technical support, contact the development team or create an issue in the repository.
