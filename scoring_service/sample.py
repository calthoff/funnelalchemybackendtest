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