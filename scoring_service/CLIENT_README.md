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

# Set data
scoring_settings = {
    "company_description": "B2B SaaS company specializing in sales automation",
    "industries": ["Technology", "Financial Services"],
    "employee_range": ["51-200", "201-500"],
    "title_keywords": ["Sales Director", "VP of Sales"]
}

prospects = [
    {
        "prospect_id": "12346",
        "full_name": "Sarah Johnson",
        "current_job": {
            "active_experience_title": "VP of Sales",
            "is_decision_maker": True
        },
        "current_company": {
            "company_industry": "Technology",
            "company_size_range": "501-1000"
        }
    }
]

# Call function
result = sc.scoring_function(scoring_settings, prospects)

# Print result
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
