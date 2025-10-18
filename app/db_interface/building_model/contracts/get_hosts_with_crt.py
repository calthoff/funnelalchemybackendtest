from crtsh import crtshAPI
import json

# Create an instance of the API client
api = crtshAPI()

# Search for a domain
#domain_to_search = 'lacounty.gov'
domain_to_search = 'google.com'
result = api.search(domain_to_search)

# Print the results (usually an array of dictionaries)
print(json.dumps(result, indent=4))

