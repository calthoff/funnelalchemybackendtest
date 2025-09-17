"""
Simple test for Funnel Alchemy Scorer module
Request from query_example.json -> Response
"""
import json
from scoring_module import score_prospects

# from scorer import score_prospects

# Load request from query_example.json
with open('query_example.json', 'r', encoding='utf-8') as f:
    request_data = json.load(f)

# Perform scoring
results = score_prospects(request_data['scoring_settings'], request_data['prospects'])

# Format response
response = [result.model_dump() for result in results]

# Output response
print(json.dumps(response, ensure_ascii=False, indent=2))
